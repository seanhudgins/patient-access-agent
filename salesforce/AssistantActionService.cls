/**
 * REST endpoint the patient assistant calls to act in Salesforce.
 * POST /services/apexrest/AssistantActions/
 *
 * Request:  {"actionType": "CREATE_CASE", "params": {"subject", "description", "priority", "accountId"?, "contactId"?}}
 * Response: "SUCCESS: Created Case 00001234" or "ERROR: <message>"
 *
 * The integration user needs Create on Case and access to this class.
 */
@RestResource(urlMapping='/AssistantActions/*')
global with sharing class AssistantActionService {

    @HttpPost
    global static String doPost() {
        try {
            Map<String, Object> body = (Map<String, Object>) JSON.deserializeUntyped(
                RestContext.request.requestBody.toString()
            );
            String actionType = (String) body.get('actionType');
            Map<String, Object> params = (Map<String, Object>) body.get('params');

            if (actionType == 'CREATE_CASE') {
                return createCase(params);
            }
            return 'ERROR: Unsupported actionType ' + actionType;
        } catch (Exception e) {
            return 'ERROR: ' + e.getMessage();
        }
    }

    private static String createCase(Map<String, Object> params) {
        Case c = new Case(
            Subject     = (String) params.get('subject'),
            Description = (String) params.get('description'),
            AccountId   = (Id) params.get('accountId'),
            ContactId   = (Id) params.get('contactId'),
            Priority    = params.containsKey('priority') ? (String) params.get('priority') : 'Medium',
            Status      = 'New',
            Origin      = 'Web'
        );
        insert c;
        c = [SELECT CaseNumber FROM Case WHERE Id = :c.Id];
        return 'SUCCESS: Created Case ' + c.CaseNumber;
    }
}
