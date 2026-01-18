"""
S3 Component Replacer

A tool to copy component files from dev/ to stage/ paths in an S3 bucket.
Reads component configurations from JSON files and processes replacements.
"""

import argparse
import json
import logging
import os
import re
import sys
from typing import Dict, List, Optional, Tuple

import boto3
from botocore.exceptions import ClientError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def extract_version(component_name: str) -> str:
    """
    Extract the last number from component name as version.
    Supports multi-digit versions (1, 2, 3+ digits).
    Only matches numbers at the end of the component name (after a dash or at the end).

    Args:
        component_name: Full component name (e.g., "Component-A-V1-19")

    Returns:
        Version string extracted from component name

    Raises:
        ValueError: If no version number is found in component name

    Examples:
        >>> extract_version("Component-A-V1-19")
        '19'
        >>> extract_version("Component-B-227")
        '227'
        >>> extract_version("Component-F-202")
        '202'
    """
    # Match the last number sequence at the end of the string
    # Must be preceded by a dash or dot to be considered a version number
    # This ensures we only match trailing version numbers, not numbers in "V1", etc.
    # Examples: "Component-A-V1-19" -> "19", "Component-B-227" -> "227"
    # But "Component-A-V1" should not match (no dash before the "1")
    match = re.search(r"[-.](\d+)$", component_name)
    if match:
        return match.group(1)
    else:
        raise ValueError(
            f"No version number found in component name: {component_name}")


def construct_file_name(pattern: str, version: str) -> str:
    """
    Replace {version} placeholder in file name pattern with actual version.

    Args:
        pattern: File name pattern with {version} placeholder
        version: Version string to replace placeholder

    Returns:
        File name with version replaced

    Example:
        >>> construct_file_name("krembo.{version}.min.js", "19")
        'krembo.19.min.js'
    """
    return pattern.replace("{version}", version)


def construct_paths(
    base_path: str, source_prefix: str = "dev", destination_prefix: str = "stage"
) -> Tuple[str, str]:
    """
    Construct source_path and destination_path from base path with configurable prefixes.

    Args:
        base_path: Base path without source/ or destination/ prefix
        source_prefix: Source path prefix (e.g., "dev", "stage", "prd")
        destination_prefix: Destination path prefix (e.g., "stage", "prd")

    Returns:
        Tuple of (source_path, destination_path)

    Example:
        >>> construct_paths("krembo/krembo_componentsV2/game_core/", "dev", "stage")
        ('dev/krembo/krembo_componentsV2/game_core/', 'stage/krembo/krembo_componentsV2/game_core/')
        >>> construct_paths("krembo/krembo_componentsV2/game_core/", "stage", "prd")
        ('stage/krembo/krembo_componentsV2/game_core/', 'prd/krembo/krembo_componentsV2/game_core/')
    """
    # Normalize leading slash
    base_path = base_path.lstrip("/")

    # Strip known prefixes (dev/, stage/, prd/, etc.)
    known_prefixes = ["dev/", "stage/", "prd/", "prod/"]
    for prefix in known_prefixes:
        if base_path.startswith(prefix):
            base_path = base_path[len(prefix):]
            break

    # Handle empty path
    if not base_path:
        return f"{source_prefix}/", f"{destination_prefix}/"

    # Ensure trailing slash
    if not base_path.endswith("/"):
        base_path += "/"

    source_path = f"{source_prefix}/{base_path}"
    destination_path = f"{destination_prefix}/{base_path}"

    return source_path, destination_path


def extract_component_identifier(component_name: str) -> str:
    """
    Extract a normalized component identifier from component name for matching.
    Removes version numbers, prefixes, and normalizes to lowercase.

    Args:
        component_name: Full component name (e.g., "KP-TroutsTreasure-V2-11")

    Returns:
        Normalized identifier (e.g., "troutstreasure")

    Example:
        >>> extract_component_identifier("KP-TroutsTreasure-V2-11")
        'troutstreasure'
        >>> extract_component_identifier("C2ServiceWrapper-202")
        'c2servicewrapper'
        >>> extract_component_identifier("KP-Phaser-3.86.0")
        'phaser'
        >>> extract_component_identifier("KP-SlotMachineV2-5")
        'slotmachine'
    """
    # Remove version numbers at the end (including dotted versions like 3.86.0)
    identifier = re.sub(r"-\d+(\.\d+)*$", "", component_name)
    # Remove common prefixes (KP-, FE-, IN-, etc.)
    identifier = re.sub(r"^[A-Z]+-", "", identifier)
    # Remove version suffixes (V2, V1, etc.) - both with and without dash
    identifier = re.sub(r"-V\d+$", "", identifier)
    identifier = re.sub(r"V\d+$", "", identifier)
    # Remove special suffixes like "MinSpinTimePOC", "HolidayDrops-Dev"
    identifier = re.sub(r"-[A-Za-z]+(-[A-Za-z]+)*$", "", identifier)
    # Normalize to lowercase
    identifier = identifier.lower()
    return identifier


def construct_s3_key_from_path_format(
    path_format: str, version: str, prefix: str = "dev"
) -> str:
    """
    Construct S3 key from path_format by replacing version placeholder and adding prefix.

    Args:
        path_format: Full path format with {0} or {version} placeholder
                    (e.g., "/krembo/krembo_components/krembo_core/krembo.{0}.min.js")
        version: Version string to replace placeholder
        prefix: Environment prefix (e.g., "dev", "stage", "prd")

    Returns:
        Full S3 key with prefix (e.g., "dev/krembo/krembo_components/krembo_core/krembo.19.min.js")

    Example:
        >>> construct_s3_key_from_path_format("/krembo/krembo_components/krembo_core/krembo.{0}.min.js", "19", "dev")
        'dev/krembo/krembo_components/krembo_core/krembo.19.min.js'
    """
    # Replace version placeholder (support both {0} and {version} for backward compatibility)
    path = path_format.replace("{0}", version).replace("{version}", version)

    # Normalize leading slash
    path = path.lstrip("/")

    # Strip known prefixes if present (dev/, stage/, prd/, etc.)
    known_prefixes = ["dev/", "stage/", "prd/", "prod/"]
    for known_prefix in known_prefixes:
        if path.startswith(known_prefix):
            path = path[len(known_prefix):]
            break

    # Add the specified prefix
    return f"{prefix}/{path}"


def copy_component_file(
    component_name: str,
    component_config: Dict[str, str],
    bucket_name: str,
    s3_client,
    source_prefix: str = "dev",
    destination_prefix: str = "stage",
    dry_run: bool = False,
) -> bool:
    """
    Copy component file from source path to destination path in S3.

    Args:
        component_name: Full component name (e.g., "Component-A-V1-19")
        component_config: Dictionary containing path_format
        bucket_name: S3 bucket name
        s3_client: Boto3 S3 client instance
        source_prefix: Source path prefix (e.g., "dev", "stage", "prd")
        destination_prefix: Destination path prefix (e.g., "stage", "prd")
        dry_run: If True, only validate and show what would be done without actually copying

    Returns:
        True if copy was successful (or would be successful in dry-run), False otherwise
    """
    try:
        if "path_format" not in component_config:
            logger.error(
                f"Missing 'path_format' in component config: {component_config}"
            )
            return False

        path_format = component_config["path_format"]

        # Extract version from component name
        version = extract_version(component_name)
        logger.info(
            f"Extracted version '{version}' from component '{component_name}'")

        # Construct S3 keys from path_format
        source_key = construct_s3_key_from_path_format(
            path_format, version, source_prefix
        )
        destination_key = construct_s3_key_from_path_format(
            path_format, version, destination_prefix
        )

        # Extract file name for logging
        file_name = os.path.basename(source_key)
        logger.info(f"Using path_format: {path_format}")
        logger.info(f"Constructed file name: {file_name}")
        logger.info(f"Source key: {source_key}")
        logger.info(f"Destination key: {destination_key}")

        # Extract directory paths for logging (remove filename from key)
        source_path = os.path.dirname(source_key).replace("\\", "/")
        destination_path = os.path.dirname(destination_key).replace("\\", "/")

        # Check if the file exists in the source using head_object
        logger.debug(
            f"Checking if file exists: s3://{bucket_name}/{source_key}")
        source_exists = False
        try:
            # Use head_object to check if the file exists
            response = s3_client.head_object(
                Bucket=bucket_name, Key=source_key)
            source_exists = True
            logger.info(f"File {file_name} found in {source_path}")
            if logger.level <= logging.DEBUG:
                logger.debug(
                    f"File size: {response.get('ContentLength', 'unknown')} bytes"
                )
                logger.debug(
                    f"Last modified: {response.get('LastModified', 'unknown')}"
                )
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "404":
                # File doesn't exist - this is expected for missing files
                source_exists = False
            elif error_code == "403":
                error_message = e.response["Error"].get(
                    "Message", "No error message")
                logger.error(
                    "Permission denied (403) when checking source file.")
                logger.error(f"Path: s3://{bucket_name}/{source_key}")
                logger.error(f"AWS Error Message: {error_message}")
                logger.error("This usually means:")
                logger.error(
                    "  1. Your AWS credentials don't have s3:GetObject permission for this path"
                )
                logger.error("  2. The bucket policy denies access")
                logger.error("  3. Your credentials are invalid or expired")
                logger.error("  4. The session token may have expired")
                logger.error(
                    "Please check your AWS credentials and S3 bucket permissions."
                )
                # Log additional debug info if available
                if logger.level <= logging.DEBUG:
                    logger.debug(f"Full error response: {e.response}")
                return False
            else:
                logger.error(
                    f"AWS error ({error_code}) when checking source file: {e.response['Error'].get('Message', str(e))}"
                )
                return False

        if not source_exists:
            logger.error(
                f"File {file_name} does not exist in {source_path}. Skipping..."
            )
            return False

        # Check if the file exists in the destination using head_object
        destination_exists = False
        try:
            s3_client.head_object(Bucket=bucket_name, Key=destination_key)
            destination_exists = True
            if dry_run:
                logger.info(
                    f"[DRY RUN] File {file_name} exists in {destination_path}. Would replace it..."
                )
            else:
                logger.info(
                    f"File {file_name} exists in {destination_path}. Replacing it..."
                )
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "404":
                # File doesn't exist - this is expected
                destination_exists = False
            elif error_code == "403":
                logger.warning(
                    "Permission denied (403) when checking destination file."
                )
                logger.warning(f"Path: s3://{bucket_name}/{destination_key}")
                logger.warning("Will attempt to copy anyway...")
            else:
                logger.warning(
                    f"AWS error ({error_code}) when checking destination file: {e.response['Error'].get('Message', str(e))}"
                )
                logger.warning("Will attempt to copy anyway...")

        if not destination_exists:
            if dry_run:
                logger.info(
                    f"[DRY RUN] File {file_name} does not exist in {destination_path}. Would upload it..."
                )
            else:
                logger.info(
                    f"File {file_name} does not exist in {destination_path}. Uploading it..."
                )

        # Copy the file from source to destination (skip in dry-run mode)
        if dry_run:
            logger.info(
                f"[DRY RUN] Would copy {file_name} from {source_path} to {destination_path}"
            )
            logger.info(f"[DRY RUN] Source: s3://{bucket_name}/{source_key}")
            logger.info(
                f"[DRY RUN] Destination: s3://{bucket_name}/{destination_key}")
            if destination_exists:
                logger.info(
                    "[DRY RUN] Note: Existing file in destination would be overwritten"
                )
            return True
        else:
            try:
                copy_source = {"Bucket": bucket_name, "Key": source_key}
                s3_client.copy_object(
                    CopySource=copy_source, Bucket=bucket_name, Key=destination_key
                )
                if destination_exists:
                    logger.info(
                        f"Successfully overwrote {file_name} in {destination_path} (replaced existing file)"
                    )
                else:
                    logger.info(
                        f"Successfully copied {file_name} from {source_path} to {destination_path} (new file)"
                    )
                return True
            except ClientError as e:
                error_code = e.response["Error"]["Code"]
                error_message = e.response["Error"].get(
                    "Message", "No error message")

                if error_code == "403":
                    logger.error("Permission denied (403) when copying file.")
                    logger.error(f"Source: s3://{bucket_name}/{source_key}")
                    logger.error(
                        f"Destination: s3://{bucket_name}/{destination_key}")
                    logger.error(f"AWS Error Message: {error_message}")
                    logger.error("")
                    logger.error("This usually means:")
                    logger.error(
                        "  1. Your AWS credentials don't have s3:GetObject permission for the source path"
                    )
                    logger.error(
                        "  2. Your AWS credentials don't have s3:PutObject permission for the destination path"
                    )
                    logger.error(
                        "  3. The bucket policy or object ACL denies access for this specific path"
                    )
                    logger.error(
                        "  4. Your credentials are invalid or expired")
                    logger.error("")
                    logger.error(
                        "Note: Path-specific permissions can cause some files to copy successfully"
                    )
                    logger.error(
                        "while others fail, even within the same bucket.")
                    logger.error(
                        "Please check your AWS credentials and S3 bucket permissions for these specific paths."
                    )

                    # Log additional debug info if available
                    if logger.level <= logging.DEBUG:
                        logger.debug(f"Full error response: {e.response}")
                    return False
                else:
                    logger.error(
                        f"AWS error ({error_code}) when copying file: {error_message}"
                    )
                    logger.error(f"Source: s3://{bucket_name}/{source_key}")
                    logger.error(
                        f"Destination: s3://{bucket_name}/{destination_key}")
                    return False

    except KeyError as e:
        logger.error(f"Missing required field in component config: {e}")
        return False
    except ValueError as e:
        logger.error(f"{e}")
        return False
    except Exception as e:
        logger.error(
            f"Unexpected error occurred while processing {component_name}: {str(e)}",
            exc_info=True,
        )
        return False


def load_component_mappings(json_file_path: str) -> Dict[str, Dict[str, str]]:
    """
    Load component mappings from JSON file.

    Args:
        json_file_path: Path to the JSON mapping file

    Returns:
        Dictionary mapping component_key to configuration
    """
    try:
        with open(json_file_path, "r", encoding="utf-8") as f:
            mappings = json.load(f)

        if not isinstance(mappings, list):
            raise ValueError(
                "JSON file must contain an array of component configurations"
            )

        # Convert list to dictionary keyed by component_key
        mapping_dict: Dict[str, Dict[str, str]] = {}
        for mapping in mappings:
            if isinstance(mapping, str):
                # Simple string format (backward compatibility) - skip as it needs component_key
                logger.warning(
                    f"Skipping string mapping without component_key: {mapping}"
                )
                continue
            elif isinstance(mapping, dict):
                if "component_key" not in mapping:
                    raise ValueError(
                        f"Missing required field 'component_key' in mapping entry: {mapping}"
                    )

                # Only support path_format format
                if "path_format" not in mapping:
                    raise ValueError(
                        f"Missing required field 'path_format' in mapping entry: {mapping}"
                    )
                mapping_dict[mapping["component_key"]] = mapping
            else:
                logger.warning(f"Skipping invalid mapping entry: {mapping}")

        return mapping_dict
    except FileNotFoundError:
        logger.error(f"Mapping file not found: {json_file_path}")
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in mapping file: {e}")
        return {}
    except ValueError:
        # Re-raise ValueError (e.g., missing component_key) so caller can handle it
        raise
    except Exception as e:
        logger.error(f"Failed to load mapping file: {e}", exc_info=True)
        return {}


def load_component_names(json_file_path: str) -> List[str]:
    """
    Load list of component names to process from JSON file.

    Args:
        json_file_path: Path to the JSON file containing component names

    Returns:
        List of component names
    """
    try:
        with open(json_file_path, "r", encoding="utf-8") as f:
            component_names = json.load(f)

        if not isinstance(component_names, list):
            raise ValueError(
                "JSON file must contain an array of component names")

        return component_names
    except FileNotFoundError:
        logger.error(f"Component names file not found: {json_file_path}")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in component names file: {e}")
        return []
    except Exception as e:
        logger.error(
            f"Failed to load component names file: {e}", exc_info=True)
        return []


def find_component_mapping(
    component_name: str, mappings: Dict[str, Dict[str, str]]
) -> Optional[Dict[str, str]]:
    """
    Find the best matching mapping configuration for a component name.
    Matches by checking if component_name starts with component_key.
    Returns the longest (most specific) matching component_key.

    Args:
        component_name: Full component name (e.g., "Component-A-V1-19")
        mappings: Dictionary of component_key -> configuration

    Returns:
        Matching configuration dictionary or None if not found

    Example:
        If mappings contain both "Component-A" and "Component-A-V1",
        and component_name is "Component-A-V1-19",
        it will return the config for "Component-A-V1" (longer match)
    """
    best_match: Optional[Tuple[str, Dict[str, str]]] = None
    best_match_length = 0

    # Find the longest matching component_key
    for component_key, config in mappings.items():
        if component_name.startswith(component_key):
            key_length = len(component_key)
            # Prefer longer matches (more specific)
            if key_length > best_match_length:
                best_match = (component_key, config)
                best_match_length = key_length

    if best_match:
        logger.debug(
            f"Matched component '{component_name}' to key '{best_match[0]}' (length: {best_match_length})"
        )
        return best_match[1]

    return None


def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments.

    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description="Copy component files from dev/ to stage/ paths in S3 bucket",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Use default file paths
  python s3_component_replacer.py
  
  # Specify custom file paths
  python s3_component_replacer.py --mapping-file custom_mapping.json --components-file custom_components.json
  
  # Use custom bucket and region
  python s3_component_replacer.py --bucket my-bucket --region us-west-2
  
  # Set log level to DEBUG
  python s3_component_replacer.py --log-level DEBUG
        """,
    )

    parser.add_argument(
        "--bucket",
        type=str,
        default="spinomenal-cdn-main",
        help="S3 bucket name (default: spinomenal-cdn-main)",
    )

    parser.add_argument(
        "--mapping-file",
        type=str,
        default="config/components_mapping.json",
        help="Path to component mappings JSON file (default: config/components_mapping.json)",
    )

    parser.add_argument(
        "--components-file",
        type=str,
        default="config/components_to_replace.json",
        help="Path to component names JSON file (default: config/components_to_replace.json)",
    )

    parser.add_argument(
        "--components",
        type=str,
        default=None,
        help="Comma-separated list of component keys to process (overrides --components-file if provided)",
    )

    parser.add_argument(
        "--region",
        type=str,
        default=None,
        help="AWS region (default: auto-detect from bucket, falls back to us-east-1)",
    )

    parser.add_argument(
        "--source-prefix",
        type=str,
        default="dev",
        help="Source path prefix (e.g., dev, stage, prd). Default: dev",
    )

    parser.add_argument(
        "--destination-prefix",
        type=str,
        default="stage",
        help="Destination path prefix (e.g., stage, prd). Default: stage",
    )

    parser.add_argument(
        "--access-key",
        type=str,
        default=None,
        help="AWS access key ID (can also use AWS_ACCESS_KEY_ID environment variable)",
    )

    parser.add_argument(
        "--secret-key",
        type=str,
        default=None,
        help="AWS secret access key (can also use AWS_SECRET_ACCESS_KEY environment variable)",
    )

    parser.add_argument(
        "--session-token",
        type=str,
        default=None,
        help="AWS session token for temporary credentials (can also use AWS_SESSION_TOKEN environment variable)",
    )

    parser.add_argument(
        "--profile",
        type=str,
        default=None,
        help="AWS profile name to use (from ~/.aws/credentials or AWS SSO). If not specified, uses default profile or credential chain",
    )

    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set the logging level (default: INFO)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Test mode: validate and show what would be done without actually copying files to S3",
    )

    return parser.parse_args()


def get_bucket_region(s3_client, bucket_name: str) -> str:
    """
    Detect the AWS region where an S3 bucket is located.

    Args:
        s3_client: Boto3 S3 client (can be in any region)
        bucket_name: Name of the S3 bucket

    Returns:
        The AWS region where the bucket is located (e.g., 'us-east-1', 'eu-west-1')
    """
    try:
        response = s3_client.head_bucket(Bucket=bucket_name)
        # The region is in the response headers
        region = (
            response.get("ResponseMetadata", {})
            .get("HTTPHeaders", {})
            .get("x-amz-bucket-region")
        )
        if region:
            logger.info(f"Detected bucket region: {region}")
            return region
        else:
            # Fallback: try to get region from bucket location
            try:
                location = s3_client.get_bucket_location(Bucket=bucket_name)
                region = location.get("LocationConstraint")
                # S3 returns None for us-east-1 (the default region)
                if region is None or region == "":
                    region = "us-east-1"
                logger.info(f"Detected bucket region from location: {region}")
                return region
            except Exception:
                logger.warning(
                    "Could not detect bucket region, defaulting to us-east-1"
                )
                return "us-east-1"
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "403":
            logger.warning(
                "Permission denied when detecting bucket region, defaulting to us-east-1"
            )
        else:
            logger.warning(
                f"Could not detect bucket region ({error_code}), defaulting to us-east-1"
            )
        return "us-east-1"
    except Exception as e:
        logger.warning(
            f"Error detecting bucket region: {e}, defaulting to us-east-1")
        return "us-east-1"


def test_s3_access(s3_client, bucket_name: str) -> bool:
    """
    Test if the S3 client can access the bucket (read permissions).

    Args:
        s3_client: Boto3 S3 client instance
        bucket_name: S3 bucket name

    Returns:
        True if access is successful, False otherwise
    """
    try:
        # Try to list objects in the bucket (requires s3:ListBucket permission)
        # Using a prefix that likely doesn't exist to minimize data transfer
        s3_client.list_objects_v2(
            Bucket=bucket_name, Prefix="__test_access__", MaxKeys=1
        )
        logger.info(
            f"Successfully verified S3 access to bucket '{bucket_name}'")
        return True
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "403":
            logger.error(
                f"Permission denied (403) when accessing bucket '{bucket_name}'"
            )
            logger.error("This usually means:")
            logger.error("  1. Your AWS credentials are invalid or expired")
            logger.error(
                "  2. Your IAM user/role doesn't have s3:ListBucket permission"
            )
            logger.error(
                "  3. The bucket policy denies access to your credentials")
        else:
            logger.warning(
                f"Could not verify bucket access: {error_code} - {e.response['Error'].get('Message', str(e))}"
            )
        return False
    except Exception as e:
        logger.warning(f"Unexpected error testing bucket access: {e}")
        return False


def get_s3_client(
    access_key: Optional[str],
    secret_key: Optional[str],
    session_token: Optional[str],
    profile: Optional[str],
    region: str,
):
    """
    Create S3 client with credentials.

    Args:
        access_key: AWS access key ID (or None to use environment/default)
        secret_key: AWS secret access key (or None to use environment/default)
        session_token: AWS session token for temporary credentials (or None)
        profile: AWS profile name (or None to use default)
        region: AWS region

    Returns:
        Boto3 S3 client instance
    """
    # If profile is specified, use boto3 session with that profile
    # This supports AWS SSO profiles and regular AWS profiles
    if profile:
        logger.info(f"Using AWS profile: {profile}")
        try:
            session = boto3.Session(profile_name=profile)
            # Verify credentials are available
            credentials = session.get_credentials()
            if credentials:
                logger.info(
                    f"Successfully loaded credentials from profile '{profile}'")
                # Log masked access key for debugging
                if credentials.access_key:
                    masked_key = (
                        credentials.access_key[:4] +
                        "..." + credentials.access_key[-4:]
                        if len(credentials.access_key) > 8
                        else "****"
                    )
                    logger.debug(f"Using access key: {masked_key}")
            else:
                logger.warning(
                    f"Profile '{profile}' found but no credentials available. You may need to run: aws sso login --profile {profile}"
                )
            return session.client("s3", region_name=region)
        except Exception as e:
            logger.error(f"Failed to load profile '{profile}': {e}")
            logger.error(
                f"Make sure you're logged in: aws sso login --profile {profile}"
            )
            raise

    # Check environment variables if not provided via arguments
    if not access_key:
        access_key = os.environ.get("AWS_ACCESS_KEY_ID")
    if not secret_key:
        secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
    if not session_token:
        session_token = os.environ.get("AWS_SESSION_TOKEN")

    # Sanitize credentials by stripping whitespace and removing all newlines
    # This prevents issues with copied/pasted credentials that may have trailing newlines
    # or newlines embedded in the middle
    if access_key:
        access_key = access_key.strip().replace("\n", "").replace("\r", "")
    if secret_key:
        secret_key = secret_key.strip().replace("\n", "").replace("\r", "")
    if session_token:
        session_token = session_token.strip().replace("\n", "").replace("\r", "")

    # Create client with credentials if provided
    if access_key and secret_key:
        logger.info(
            "Using AWS credentials from arguments or environment variables")
        # Log masked access key for debugging
        masked_key = (
            access_key[:4] + "..." +
            access_key[-4:] if len(access_key) > 8 else "****"
        )
        logger.debug(f"Using access key: {masked_key}")
        if session_token:
            logger.debug("Using session token (temporary credentials)")

        client_kwargs = {
            "aws_access_key_id": access_key,
            "aws_secret_access_key": secret_key,
            "region_name": region,
        }
        # Add session token if provided (for temporary credentials)
        if session_token:
            client_kwargs["aws_session_token"] = session_token
            logger.info("Using AWS session token for temporary credentials")

        return boto3.client("s3", **client_kwargs)
    else:
        logger.info(
            "Using default AWS credential chain (AWS CLI config, IAM roles, AWS SSO, etc.)"
        )
        return boto3.client("s3", region_name=region)


def main() -> int:
    """
    Main function to orchestrate the component replacement process.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    args = parse_arguments()

    # Set logging level
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    # Get the directory where this script is located (src/)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Get the project root directory (parent of src/)
    project_root = os.path.dirname(script_dir)

    # Resolve file paths (use project root for relative paths)
    if os.path.isabs(args.mapping_file):
        mapping_file_path = args.mapping_file
    else:
        # Resolve relative paths from project root
        mapping_file_path = os.path.join(project_root, args.mapping_file)

    if os.path.isabs(args.components_file):
        components_file_path = args.components_file
    else:
        # Resolve relative paths from project root
        components_file_path = os.path.join(project_root, args.components_file)

    logger.info(f"Loading component mappings from: {mapping_file_path}")
    logger.info(f"Loading component names from: {components_file_path}")
    logger.info(f"Using S3 bucket: {args.bucket}")
    logger.info(f"Source prefix: {args.source_prefix}")
    logger.info(f"Destination prefix: {args.destination_prefix}")

    # Sanitize credentials from command-line arguments (strip whitespace and remove newlines)
    # This handles cases where credentials are copied/pasted with embedded newlines
    access_key = (
        args.access_key.strip().replace("\n", "").replace("\r", "")
        if args.access_key
        else None
    )
    secret_key = (
        args.secret_key.strip().replace("\n", "").replace("\r", "")
        if args.secret_key
        else None
    )
    session_token = (
        args.session_token.strip().replace("\n", "").replace("\r", "")
        if args.session_token
        else None
    )

    # Determine region: use provided region, or auto-detect from bucket
    initial_region = args.region if args.region else "us-east-1"

    # Initialize S3 client with initial region (us-east-1 or user-specified)
    s3_client = get_s3_client(
        access_key, secret_key, session_token, args.profile, initial_region
    )

    # Auto-detect bucket region if not explicitly provided
    if not args.region:
        detected_region = get_bucket_region(s3_client, args.bucket)
        if detected_region != initial_region:
            logger.info(
                f"Recreating S3 client with detected region: {detected_region}")
            s3_client = get_s3_client(
                access_key, secret_key, session_token, args.profile, detected_region
            )
        logger.info(f"Using AWS region: {detected_region}")
    else:
        logger.info(f"Using AWS region: {args.region} (user-specified)")

    # Test S3 access before processing components
    logger.info("Testing S3 access...")
    bucket_access_ok = test_s3_access(s3_client, args.bucket)
    if not bucket_access_ok:
        logger.error(
            "Failed to access S3 bucket. Please check your credentials and permissions."
        )
        logger.error("Required IAM permissions:")
        logger.error(
            "  - s3:ListBucket (to verify access and check if files exist)")
        logger.error(
            "  - s3:GetObject (required by copy_object to read source files)")
        logger.error(
            "  - s3:PutObject (required by copy_object to write destination files)"
        )
        return 1
    else:
        logger.info("✓ Initial bucket access test passed")

    if args.dry_run:
        logger.info("=" * 80)
        logger.info("DRY RUN MODE - No changes will be made to S3")
        logger.info("=" * 80)
    logger.info("-" * 80)

    # Load component mappings
    component_mappings = load_component_mappings(mapping_file_path)

    if not component_mappings:
        logger.error("No component mappings found. Exiting.")
        return 1

    logger.info(f"Loaded {len(component_mappings)} component mapping(s)")

    # Load component names to process
    if args.components:
        # Use components from command line (comma-separated)
        component_names = [comp.strip() for comp in args.components.split(",") if comp.strip()]
        logger.info(f"Using components from command line: {len(component_names)} component(s)")
    else:
        # Load from file
        component_names = load_component_names(components_file_path)

    if not component_names:
        logger.error("No component names found. Exiting.")
        return 1

    logger.info(f"Found {len(component_names)} component(s) to process\n")

    # Process each component
    success_count = 0
    failure_count = 0
    not_found_count = 0
    successful_components = []
    failed_components = []

    for i, component_name in enumerate(component_names, 1):
        logger.info(
            f"\n[{i}/{len(component_names)}] Processing: {component_name}")
        logger.info("-" * 80)

        # Find matching mapping
        component_config = find_component_mapping(
            component_name, component_mappings)

        if not component_config:
            logger.error(f"No mapping found for component '{component_name}'")
            not_found_count += 1
            failure_count += 1
            failed_components.append(component_name)
            continue

        if copy_component_file(
            component_name,
            component_config,
            args.bucket,
            s3_client,
            source_prefix=args.source_prefix,
            destination_prefix=args.destination_prefix,
            dry_run=args.dry_run,
        ):
            success_count += 1
            successful_components.append(component_name)
        else:
            failure_count += 1
            failed_components.append(component_name)

    # Summary
    logger.info("\n" + "=" * 80)
    if args.dry_run:
        logger.info("DRY RUN SUMMARY (No changes were made)")
    else:
        logger.info("SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Total components to process: {len(component_names)}")
    logger.info(f"Successful: {success_count}")
    logger.info(f"Failed: {failure_count}")

    if successful_components:
        logger.info(
            f"\n✓ Successfully processed components ({len(successful_components)}):"
        )
        for comp in successful_components:
            logger.info(f"  - {comp}")

    if failed_components:
        logger.info(f"\n✗ Failed components ({len(failed_components)}):")
        for comp in failed_components:
            logger.info(f"  - {comp}")
        logger.info(
            "\nNote: If some components succeeded and others failed with permission errors,"
        )
        logger.info(
            "this usually indicates path-specific IAM permissions or bucket policies."
        )
        logger.info(
            "Check the error messages above for the specific paths that failed."
        )

    if not_found_count > 0:
        logger.info(f"  - No mapping found: {not_found_count}")
    if args.dry_run:
        logger.info(
            "\nTo actually perform the copy operations, run without --dry-run flag"
        )
    logger.info("=" * 80)

    return 0 if failure_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
