rm -fr target
mkdir target
cd target
zip get_forecast.zip ../get_forecast.py
aws s3 --profile jim-zucker cp get_forecast.zip s3://jimzucker-github-getforecast

# Steps to create an IAM Role with permissions to write to this S3 bucket

# 1) Go to the bucket that you want to share the permissions of, and get its ARN.
# 2) Go to IAM -> Roles -> Create Role -> AWS Account -> Another AWS Account 
#    And enter the Account ID of the account you want to give permissions to.
#    Require External ID, and create a unique password or phrase you can share with this user.
# 3) Create a Policy
#       Service - S3
#       Access Level - PutObject, GetObject, and ListBucket
#       Resources - Specify ARN of the S3 Bucket, as well as the object that will be being replaced.
#       Give the role a name and a description, and create role
# 4) Share your external ID with the third party, as well as the ARN of the IAM Role that was created.