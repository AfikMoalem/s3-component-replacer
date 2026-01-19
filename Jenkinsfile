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
        
        [$class: 'org.biouno.unochoice.ChoiceParameter',
         choiceType: 'PT_MULTI_SELECT',
         name: 'COMPONENTS_LIST',
         description: 'Select one or more components to deploy',
         filterable: true,
         script: [$class: 'GroovyScript',
                  fallbackScript: [class: 'org.jenkinsci.plugins.scriptsecurity.sandbox.groovy.SecureGroovyScript',
                                   script: 'return ["FE-AutoBetMenu", "FE-BetSlip", "FE-BuyFeature", "FE-C2LoadingWrapper", "FE-C2ServiceWrapper", "FE-FreeRounds", "FE-GameLoadingScreen", "FE-InterService", "FE-KremboBuyFeature", "FE-KremboGameLoadingScreen", "FE-KremboGameRibbon", "FE-KremboFeatureBox", "FE-KremboLoadingWrapper", "FE-KremboMessageScreen", "FE-KremboServiceWrapper", "FE-KremboRequestLoadingScreen", "FE-MessageScreen", "FE-PaytableHelpPage", "FE-PaytableHelpage", "FE-PaytableLoader", "FE-PromoTool", "FE-RequestLoadingScreen", "FE-FeatureBox", "FE-TicketGenerator", "FE-TicketHistory", "KP-BookOfPiggyBank", "KP-BookOfPiggyBank-V2", "KP-BookOfPiggyBankV2", "KP-BookOfRebirth", "KP-BookOfRebirth-V2", "KP-BookOfRebirthV2", "KP-ClassicFruits-V2", "KP-DragonsCharms", "KP-DragonsCharms-V2", "KP-DragonsCharmsV2", "KP-FruitsCollection", "KP-FruitsCollection-10E-V2", "KP-FruitsCollection-V2", "KP-HoldNHit3x3-V2", "KP-HoldNHitV2", "KP-KitsunesScrollsV2", "KP-Krembo", "KP-Krembo-V2", "KP-KremboCore", "KP-KremboV2", "KP-MajesticKing", "KP-MajesticKing-V2", "KP-OneReel", "KP-OneReel-V2", "KP-Phaser", "KP-PhaserEngine", "KP-PowerHoldNHit-V2", "KP-Retro777", "KP-Retro777-V2", "KP-SnatchTheGold-V2", "KP-SlotMachine", "KP-SlotMachine-V2", "KP-SlotMachineV2", "KP-Slotmachine", "KP-Slotmachine-V2", "KP-StoryOfGaia", "KP-StoryOfGaia-V2", "KP-StoryOfGaiaV2", "KP-Tower", "KP-Tower-V2", "KP-TroutsTreasure", "KP-TroutsTreasure-V2", "KP-WolfFang", "KP-WolfFang-V2"]',
                                   sandbox: true],
                  script: [class: 'org.jenkinsci.plugins.scriptsecurity.sandbox.groovy.SecureGroovyScript',
                           script: 'return ["FE-AutoBetMenu", "FE-BetSlip", "FE-BuyFeature", "FE-C2LoadingWrapper", "FE-C2ServiceWrapper", "FE-FreeRounds", "FE-GameLoadingScreen", "FE-InterService", "FE-KremboBuyFeature", "FE-KremboGameLoadingScreen", "FE-KremboGameRibbon", "FE-KremboFeatureBox", "FE-KremboLoadingWrapper", "FE-KremboMessageScreen", "FE-KremboServiceWrapper", "FE-KremboRequestLoadingScreen", "FE-MessageScreen", "FE-PaytableHelpPage", "FE-PaytableHelpage", "FE-PaytableLoader", "FE-PromoTool", "FE-RequestLoadingScreen", "FE-FeatureBox", "FE-TicketGenerator", "FE-TicketHistory", "KP-BookOfPiggyBank", "KP-BookOfPiggyBank-V2", "KP-BookOfPiggyBankV2", "KP-BookOfRebirth", "KP-BookOfRebirth-V2", "KP-BookOfRebirthV2", "KP-ClassicFruits-V2", "KP-DragonsCharms", "KP-DragonsCharms-V2", "KP-DragonsCharmsV2", "KP-FruitsCollection", "KP-FruitsCollection-10E-V2", "KP-FruitsCollection-V2", "KP-HoldNHit3x3-V2", "KP-HoldNHitV2", "KP-KitsunesScrollsV2", "KP-Krembo", "KP-Krembo-V2", "KP-KremboCore", "KP-KremboV2", "KP-MajesticKing", "KP-MajesticKing-V2", "KP-OneReel", "KP-OneReel-V2", "KP-Phaser", "KP-PhaserEngine", "KP-PowerHoldNHit-V2", "KP-Retro777", "KP-Retro777-V2", "KP-SnatchTheGold-V2", "KP-SlotMachine", "KP-SlotMachine-V2", "KP-SlotMachineV2", "KP-Slotmachine", "KP-Slotmachine-V2", "KP-StoryOfGaia", "KP-StoryOfGaia-V2", "KP-StoryOfGaiaV2", "KP-Tower", "KP-Tower-V2", "KP-TroutsTreasure", "KP-TroutsTreasure-V2", "KP-WolfFang", "KP-WolfFang-V2"]',
                           sandbox: true]]],
        
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
                    if (!params.COMPONENTS_LIST) {
                        error("No components specified. Please select at least one component.")
                    }
                    
                    // Active Choices multi-select can return array or comma-separated string
                    def components = []
                    if (params.COMPONENTS_LIST instanceof List || params.COMPONENTS_LIST instanceof String[]) {
                        components = params.COMPONENTS_LIST.collect { it.toString().trim() }.findAll { it }
                    } else {
                        // Comma-separated string
                        def componentsText = params.COMPONENTS_LIST.toString().trim()
                        if (componentsText.isEmpty()) {
                            error("No components specified. Please select at least one component.")
                        }
                        components = componentsText.split(',').collect { it.trim() }.findAll { it }
                    }
                    
                    if (components.isEmpty()) {
                        error("No valid components found. Please check your selection.")
                    }
                    
                    // Store in environment variable
                    env.SELECTED_COMPONENTS = components.join(',')
                    env.COMPONENTS_COUNT = components.size().toString()
                    
                    echo "Selected ${components.size()} component(s):"
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
                        python src/s3_component_replacer.py ^
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

