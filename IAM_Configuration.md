# Steps to create an IAM Role with permissions to write to this S3 bucket
1) Go to the bucket that you want to share the permissions of, and get its ARN.
2) Go to IAM -> Roles -> Create Role -> AWS Account -> Another AWS Account 
    And enter the Account ID of the account you want to give permissions to.
    Require External ID, and create a unique password or phrase you can share with this user.
3) Create a Policy
    Service - S3
    Access Level - PutObject, GetObject, DeleteObject, and ListBucket. If your bucket has ACL's, then you also need PutObjectACL and GetObjectACL.
    Resources - Specify ARN of the S3 Bucket, as well as the object that will be being replaced.
    Attach the policy to a role.
    Give the role a name and a description, and make sure that the trusted relationships of the role enables the STSAssumeRole Action to the Principal AWS Account, and create role
4) Share your external ID with the third party, as well as the ARN of the IAM Role that was created.
5) Ask the third party for the ARN of their IAM USER that will be ASSUMING your ROLE. Go to the role you created, go to its Trust Relationship, and change the Principal from the root of their AWS account the ARN of the IAM user that they have created. ROOT USERS CANNOT ASSUME ROLES. 



The trust Policy of your S3 Bucket should look like this.

```
{
    "Version": "2012-10-17",
    "Id": "AllowOtherAWSAccountToAccessS3Bucket",
    "Statement": [
        {
            "Sid": "AllowAccess",
            "Effect": "Allow",
            "Principal": {
                "AWS": "arn:aws:iam::<ACCOUNT_ID>:user/<XYZ>"
            },
            "Action": [
                "s3:PutObject",
                "s3:GetObject",
                "s3:DeleteObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "ARN OF THE BUCKET HERE/*",
                "ARN OF THE BUCKET HERE"         
            ]
        }
    ]
}
```

