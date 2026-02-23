#imports for the script
import json
import boto3
import requests

#parameters - in the future they can be moved to the config file so that all the variables are in one place and can be easily changed
url = "https://honolulu-api.datausa.io/tesseract/data.jsonrecords?cube=acs_yg_total_population_1&drilldowns=Year%2CNation&locale=en&measures=Population"
bucket = "kbannu-test1"
s3_key = "datausa/acs_yg_total_population_1.json"

#get the data from the URL (API call)
resp = requests.get(url, timeout=30)
data = resp.json()
json_string = json.dumps(data, indent=2)

#get access keys from secrets manager and upload the file to s3
try:
    from pyspark.dbutils import DBUtils
    from pyspark.sql import SparkSession
    dbutils = DBUtils(SparkSession.builder.getOrCreate())
    s3 = boto3.client("s3", aws_access_key_id=dbutils.secrets.get("quest-aws", "access-key-id"), aws_secret_access_key=dbutils.secrets.get("quest-aws", "secret-access-key"))
except Exception:
    s3 = boto3.client("s3")
s3.put_object(Bucket=bucket, Key=s3_key, Body=json_string, ContentType="application/json")
print("Uploaded to s3://" + bucket + "/" + s3_key)