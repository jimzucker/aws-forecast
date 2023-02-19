rm -fr target
mkdir target
cd target
zip get_forecast.zip ../get_forecast.py
aws s3 --profile jim-zucker cp get_forecast.zip s3://jimzucker-github-getforecast
cd ..

# Check IAM Configuration for Instructions on how to upload updated code to this bucket.

