# Auth Testing Playbook (LedgerStream AI)

## JWT email/password
curl -c cookies.txt -X POST $API/api/auth/login -H "Content-Type: application/json" -d '{"email":"demo@ledgerstream.ai","password":"LedgerDemo#2026"}'
curl -b cookies.txt $API/api/auth/me
- Login sets httpOnly access_token (15 min) + refresh_token (7 days). bcrypt hashes start with $2b$.
- 5 failed logins per ip:email => 15 min lockout (429).

## Emergent Google session (simulate)
mongosh test_database --eval '
var userId="test-user-"+Date.now(); var tok="test_session_"+Date.now();
db.users.insertOne({user_id:userId,email:"test.user."+Date.now()+"@example.com",name:"Test User",plan:"free",subscription_status:"trial",pages_used:0,created_at:new Date()});
db.user_sessions.insertOne({user_id:userId,session_token:tok,expires_at:new Date(Date.now()+7*864e5),created_at:new Date()});
print(tok)'
curl -H "Authorization: Bearer <tok>" $API/api/auth/me
Browser: add cookie session_token=<tok> (httpOnly, secure, sameSite None) then open /dashboard.

## Cleanup
db.users.deleteMany({email:/test\.user\./}); db.user_sessions.deleteMany({session_token:/test_session/});
