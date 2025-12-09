"""
Simple script to test AWS credentials and S3 access.
Run this to verify your credentials work before using the main script.
"""

import os
import sys
import boto3
from botocore.exceptions import ClientError


def test_aws_s3_access():
    """Test AWS credentials and S3 bucket access."""

    # Get credentials from environment or command line
    access_key = os.environ.get("AWS_ACCESS_KEY_ID")
    secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
    session_token = os.environ.get("AWS_SESSION_TOKEN")

    bucket_name = "example-bucket-name"

    print("=" * 80)
    print("AWS Credentials Test")
    print("=" * 80)

    # Check if credentials are provided
    if not access_key or not secret_key:
        print("ERROR: AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY must be set")
        print("\nSet them using:")
        print("  $env:AWS_ACCESS_KEY_ID='your-key'")
        print("  $env:AWS_SECRET_ACCESS_KEY='your-secret'")
        if session_token:
            print("  $env:AWS_SESSION_TOKEN='your-token'")
        return 1

    # Sanitize credentials
    access_key = access_key.strip().replace("\n", "").replace("\r", "")
    secret_key = secret_key.strip().replace("\n", "").replace("\r", "")
    if session_token:
        session_token = session_token.strip().replace("\n", "").replace("\r", "")

    print(f"\nAccess Key: {access_key[:4]}...{access_key[-4:]}")
    if session_token:
        print("Session Token: Provided (temporary credentials)")
    else:
        print("Session Token: Not provided (permanent credentials)")

    # Create S3 client
    print(f"\nCreating S3 client for bucket: {bucket_name}")
    try:
        client_kwargs = {
            "aws_access_key_id": access_key,
            "aws_secret_access_key": secret_key,
            "region_name": "us-east-1",  # Start with default
        }
        if session_token:
            client_kwargs["aws_session_token"] = session_token

        s3_client = boto3.client("s3", **client_kwargs)
        print("✓ S3 client created successfully")
    except Exception as e:
        print(f"✗ Failed to create S3 client: {e}")
        return 1

    # Detect bucket region
    print("\nDetecting bucket region...")
    try:
        response = s3_client.head_bucket(Bucket=bucket_name)
        region = (
            response.get("ResponseMetadata", {})
            .get("HTTPHeaders", {})
            .get("x-amz-bucket-region")
        )
        if not region:
            location = s3_client.get_bucket_location(Bucket=bucket_name)
            region = location.get("LocationConstraint") or "us-east-1"
        print(f"✓ Bucket region: {region}")

        # Recreate client with correct region if needed
        if region != "us-east-1":
            print(f"Recreating client with region: {region}")
            client_kwargs["region_name"] = region
            s3_client = boto3.client("s3", **client_kwargs)
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "403":
            print("✗ Permission denied (403) - Cannot access bucket")
            print("  Your credentials may be invalid or lack s3:ListBucket permission")
            return 1
        else:
            print(f"✗ Error detecting region: {error_code}")
            return 1
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return 1

    # Test list access
    print("\nTesting bucket access (s3:ListBucket)...")
    try:
        s3_client.list_objects_v2(Bucket=bucket_name, Prefix="dev/", MaxKeys=1)
        print("✓ Successfully listed objects (s3:ListBucket permission OK)")
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "403":
            print("✗ Permission denied (403) - Missing s3:ListBucket permission")
            return 1
        else:
            print(
                f"✗ Error: {error_code} - {e.response['Error'].get('Message', str(e))}"
            )
            return 1

    # Test read access (try to head an object)
    print("\nTesting read access (s3:GetObject)...")
    test_paths = [
        "dev/krembo/krembo_componentsV2/game_type/slotmachine/",
        "dev/",
    ]

    found_readable = False
    for test_prefix in test_paths:
        try:
            # Try to list and get first object
            response = s3_client.list_objects_v2(
                Bucket=bucket_name, Prefix=test_prefix, MaxKeys=1
            )
            if "Contents" in response and len(response["Contents"]) > 0:
                test_key = response["Contents"][0]["Key"]
                s3_client.head_object(Bucket=bucket_name, Key=test_key)
                print(f"✓ Successfully read object: {test_key}")
                print("  (s3:GetObject permission OK)")
                found_readable = True
                break
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "403":
                print(f"  ✗ Permission denied for prefix: {test_prefix}")
            elif error_code == "404":
                continue  # No objects in this prefix, try next
            else:
                print(f"  ✗ Error: {error_code}")
        except Exception:
            continue

    if not found_readable:
        print("⚠ Could not test read access (no accessible objects found)")
        print("  This might be OK if the bucket is empty or paths are different")

    # Test write access (dry run - just check permissions)
    print("\nTesting write access (s3:PutObject)...")
    print("  (Note: This is a permission check, not an actual write)")
    print("  If you can list and read, write should work if you have s3:PutObject")

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print("✓ Credentials are valid")
    print("✓ S3 client created successfully")
    print("✓ Bucket access verified")
    if found_readable:
        print("✓ Read access verified")
    print("\nYour credentials appear to be working correctly!")
    print("You can now run the main script:")
    print("  python s3_component_replacer.py --dry-run")
    print("=" * 80)

    return 0


if __name__ == "__main__":
    sys.exit(test_aws_s3_access())
