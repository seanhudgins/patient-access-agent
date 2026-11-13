// Demo data for a Salesforce Developer org: the four synthetic demo patients as Contacts, plus one
// sample Case so the Cases list isn't empty before the first handoff. Synthetic data only.
//
// Run once: gear icon -> Developer Console -> Debug -> Open Execute Anonymous Window -> paste -> Execute.
// Safe to rerun: it skips patients that already exist.

Account clinic = new Account(Name = 'Sierra Valley Health - Demo Patients');
List<Account> existing = [SELECT Id FROM Account WHERE Name = :clinic.Name LIMIT 1];
if (existing.isEmpty()) { insert clinic; } else { clinic = existing[0]; }

List<Contact> patients = new List<Contact>{
    new Contact(FirstName = 'Maria', LastName = 'Lopez',  Birthdate = Date.newInstance(1984, 3, 12), Phone = '555-301-1001', AccountId = clinic.Id),
    new Contact(FirstName = 'James', LastName = 'Okafor', Birthdate = Date.newInstance(1971, 11, 2), Phone = '555-301-1002', AccountId = clinic.Id),
    new Contact(FirstName = 'Alex',  LastName = 'Kim',    Birthdate = Date.newInstance(1995, 7, 28), Phone = '555-301-1003', AccountId = clinic.Id),
    new Contact(FirstName = 'Sarah', LastName = 'Bellum', Birthdate = Date.newInstance(1985, 6, 14), Phone = '555-301-1004', AccountId = clinic.Id)
};
Set<String> have = new Set<String>();
for (Contact c : [SELECT FirstName, LastName FROM Contact WHERE AccountId = :clinic.Id]) {
    have.add(c.FirstName + ' ' + c.LastName);
}
List<Contact> toInsert = new List<Contact>();
for (Contact c : patients) {
    if (!have.contains(c.FirstName + ' ' + c.LastName)) { toInsert.add(c); }
}
insert toInsert;

if ([SELECT COUNT() FROM Case WHERE Subject LIKE 'DEMO:%'] == 0) {
    insert new Case(
        Subject = 'DEMO: Nurse line - headache 3 days, BP medication concern',
        Description = 'Example of a handoff from the patient access agent. Verified caller asks about a 3-day '
            + 'headache and says their blood pressure medication isn\'t working. No clinical advice given.',
        Priority = 'High', Status = 'New', Origin = 'Web', AccountId = clinic.Id
    );
}
System.debug('Demo data ready: ' + toInsert.size() + ' new patients.');
