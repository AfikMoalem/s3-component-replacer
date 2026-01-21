// Jenkinsfile using Active Choices plugin for dynamic parameter selection
// Define properties before pipeline block for Active Choices support

properties([
    parameters([
        [$class: 'org.biouno.unochoice.ChoiceParameter',
         choiceType: 'PT_SINGLE_SELECT',
         name: 'SOURCE_ENV',
         description: 'Source environment',
         filterable: false,
         script: [$class: 'GroovyScript',
                  fallbackScript: [class: 'org.jenkinsci.plugins.scriptsecurity.sandbox.groovy.SecureGroovyScript',
                                   script: '',
                                   sandbox: true],
                  script: [class: 'org.jenkinsci.plugins.scriptsecurity.sandbox.groovy.SecureGroovyScript',
                           script: "return ['dev', 'stage']",
                           sandbox: true]]],
        
        [$class: 'org.biouno.unochoice.CascadeChoiceParameter',
         choiceType: 'PT_SINGLE_SELECT',
         name: 'DEST_ENV',
         description: 'Destination environment (depends on source)',
         filterable: false,
         referencedParameters: 'SOURCE_ENV',
         script: [$class: 'GroovyScript',
                  fallbackScript: [class: 'org.jenkinsci.plugins.scriptsecurity.sandbox.groovy.SecureGroovyScript',
                                   script: '',
                                   sandbox: true],
                  script: [class: 'org.jenkinsci.plugins.scriptsecurity.sandbox.groovy.SecureGroovyScript',
                           script: '''
                               def sourceEnv = SOURCE_ENV ?: 'dev'
                               if (sourceEnv == 'dev') {
                                   return ['stage', 'live']
                               } else if (sourceEnv == 'stage') {
                                   return ['live']
                               } else {
                                   return ['stage', 'live']
                               }
                           ''',
                           sandbox: true]]],
        
        [$class: 'TextParameterDefinition',
         name: 'COMPONENTS_LIST',
         defaultValue: '',
         description: '''Enter component keys (one per line or comma-separated):
Examples:
FE-C2ServiceWrapper-123
KP-SlotMachine-V2-456
FE-InterService-789

Note: Component names must include version numbers (e.g., -123, -456)'''],
        
        [$class: 'StringParameterDefinition',
         name: 'AWS_PROFILE',
         defaultValue: '',
         description: 'AWS profile name (leave empty to use default credential chain)'],
        
        [$class: 'BooleanParameterDefinition',
         name: 'DRY_RUN',
         defaultValue: false,
         description: 'Dry run mode (test without making changes)'],
        
        [$class: 'StringParameterDefinition',
         name: 'S3_BUCKET',
         defaultValue: 'spinomenal-cdn-main',
         description: 'S3 bucket name']
    ])
])

pipeline {
    agent any

    environment {
        PYTHONUNBUFFERED = '1'
    }

    stages {
        stage('Parse Components') {
            steps {
                script {
                    if (!params.COMPONENTS_LIST || params.COMPONENTS_LIST.trim().isEmpty()) {
                        error("No components specified. Please provide at least one component key.")
                    }
                    
                    // Parse components (support both newline and comma-separated)
                    def componentsText = params.COMPONENTS_LIST.trim()
                    def components = []
                    
                    // Try comma-separated first
                    if (componentsText.contains(',')) {
                        components = componentsText.split(',').collect { it.trim() }.findAll { it }
                    } else {
                        // Newline-separated
                        components = componentsText.split('\n').collect { it.trim() }.findAll { it }
                    }
                    
                    if (components.isEmpty()) {
                        error("No valid components found. Please check your input.")
                    }
                    
                    // Store in environment variable
                    env.SELECTED_COMPONENTS = components.join(',')
                    env.COMPONENTS_COUNT = components.size().toString()
                    
                    echo "Parsed ${components.size()} component(s):"
                    components.each { comp ->
                        echo "  - ${comp}"
                    }
                }
            }
        }
        
        stage('Validate Parameters') {
            steps {
                script {
                    if (params.SOURCE_ENV == params.DEST_ENV) {
                        error("Source and destination environments cannot be the same!")
                    }
                    
                    echo """
                    ========================================
                    Build Parameters:
                    ========================================
                    Source Environment: ${params.SOURCE_ENV}
                    Destination Environment: ${params.DEST_ENV}
                    Components Count: ${env.COMPONENTS_COUNT}
                    S3 Bucket: ${params.S3_BUCKET}
                    AWS Profile: ${params.AWS_PROFILE ?: 'default'}
                    Dry Run: ${params.DRY_RUN}
                    ========================================
                    """
                }
            }
        }
        
        stage('Deploy Components') {
            steps {
                script {
                    def profileArg = params.AWS_PROFILE ? "--profile ${params.AWS_PROFILE}" : ""
                    def dryRunArg = params.DRY_RUN ? "--dry-run" : ""
                    
                    bat """
                        python -m pip install --quiet boto3 botocore ^
                        && python src/s3_component_replacer.py ^
                            --bucket ${params.S3_BUCKET} ^
                            --source-prefix ${params.SOURCE_ENV} ^
                            --destination-prefix ${params.DEST_ENV} ^
                            --mapping-file config/components_mapping.json ^
                            --components ${env.SELECTED_COMPONENTS} ^
                            ${profileArg} ^
                            ${dryRunArg} ^
                            --log-level INFO
                    """
                }
            }
        }
    }
    
    post {
        success {
            echo '✓ Component deployment completed successfully!'
        }
        failure {
            echo '✗ Component deployment failed. Check the logs above for details.'
        }
    }
}

