"""Show IAM policies attached to the current credentials."""
import dotenv
from pathlib import Path

dotenv.load_dotenv(Path(__file__).parent.parent / ".env")

import boto3

iam = boto3.client("iam")
username = iam.get_user()["User"]["UserName"]
print("IAM user:", username)

attached = iam.list_attached_user_policies(UserName=username)["AttachedPolicies"]
print("\nAttached managed policies:")
for p in attached:
    print(" ", p["PolicyName"], "-", p["PolicyArn"])

inline = iam.list_user_policies(UserName=username)["PolicyNames"]
print("\nInline policies:", inline or "(none)")

groups = iam.list_groups_for_user(UserName=username)["Groups"]
print("\nGroups:", [g["GroupName"] for g in groups] or "(none)")
for g in groups:
    gp = iam.list_attached_group_policies(GroupName=g["GroupName"])["AttachedPolicies"]
    print(f"  {g['GroupName']} managed:", [p["PolicyName"] for p in gp])
    gi = iam.list_group_policies(GroupName=g["GroupName"])["PolicyNames"]
    print(f"  {g['GroupName']} inline:", gi or "(none)")
