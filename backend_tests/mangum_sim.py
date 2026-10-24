# Simulates AWS Lambda invocations of lambda_handler (API Gateway HTTP API v2 events) to check warm-invocation behavior
import os, sys, time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
os.environ["DATABASE_URL"] = os.environ["MONGO_URL"]
sys.path.insert(0, "/app/api")
import lambda_function as lf  # noqa

calls = {"startup": 0}
orig = lf.seed_demo_user
async def counted():
    calls["startup"] += 1
    await orig()
lf.seed_demo_user = counted


def ev(path):
    return {
        "version": "2.0", "routeKey": "$default", "rawPath": path, "rawQueryString": "",
        "headers": {"host": "x.lambda-url.us-east-1.on.aws", "x-forwarded-proto": "https"},
        "requestContext": {"http": {"method": "GET", "path": path, "protocol": "HTTP/1.1", "sourceIp": "1.1.1.1", "userAgent": "t"},
                           "domainName": "x", "stage": "$default", "requestId": "r", "accountId": "1", "apiId": "a", "time": "", "timeEpoch": 0},
        "isBase64Encoded": False, "body": None,
    }


class Ctx:
    aws_request_id = "1"
    def get_remaining_time_in_millis(self):
        return 30000


for i in range(3):
    t = time.time()
    r = lf.lambda_handler(ev("/api/health"), Ctx())
    print(i, r["statusCode"], r["body"][:80], f"{(time.time()-t)*1000:.0f}ms", "seed_calls=", calls["startup"])
r = lf.lambda_handler(ev("/api/auth/me"), Ctx())
print("me", r["statusCode"], r["body"][:80])
