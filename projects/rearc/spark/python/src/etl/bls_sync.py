import hashlib
import boto3
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

user_agent = "bls-sync/1.0 (contact: krishnaveni.nkatte@gmail.com)"
email = "krishnaveni.nkatte@gmail.com"
index_url = "https://download.bls.gov/pub/time.series/pr/"
prefix = "bls/pr"
bucket = "kbannu-test1"

session = requests.Session()
session.headers["User-Agent"] = user_agent
session.headers["From"] = email

html = session.get(index_url).text
soup = BeautifulSoup(html, "html.parser")

urls = []
for a in soup.find_all("a", href=True):
    href = a["href"]
    if href.endswith("/") or href == "../":
        continue
    urls.append(urljoin(index_url, href))
    

urls = sorted(set(urls))


prefix = prefix.strip("/")

remotes = []
for url in urls:
    path = urlparse(url).path.lstrip("/")
    if not path:
        path = hashlib.sha256(url.encode("utf-8")).hexdigest()
    s3_key = f"{prefix}/{path}" if prefix else path
    try:
        info = session.head(url, timeout=60)
        if info.status_code in (403, 405):
            raise Exception()
    except Exception:
        info = session.get(url, stream=True, timeout=60)
    info.raise_for_status()
    remotes.append({
        "url": url,
        "s3_key": s3_key,
        "last_modified": info.headers.get("Last-Modified"),
    })

try:
    from pyspark.dbutils import DBUtils
    from pyspark.sql import SparkSession
    dbutils = DBUtils(SparkSession.builder.getOrCreate())
    s3 = boto3.client("s3", aws_access_key_id=dbutils.secrets.get("quest-aws", "access-key-id"), aws_secret_access_key=dbutils.secrets.get("quest-aws", "secret-access-key"))
except Exception:
    s3 = boto3.client("s3")
#s3 = boto3.client("s3")

existing_s3 = {}
resp = s3.list_objects_v2(Bucket=bucket, Prefix=prefix + "/")
for obj in resp.get("Contents") or []:
    existing_s3[obj["Key"]] = {}


for key in existing_s3:
    try:
        head = s3.head_object(Bucket=bucket, Key=key)
        existing_s3[key]["source_last_modified"] = (head.get("Metadata") or {}).get("source-last-modified")
    except Exception:
        existing_s3[key]["source_last_modified"] = None


remote_keys = {r["s3_key"] for r in remotes}
inserted = updated = deleted = 0

for r in remotes:
    key = r["s3_key"]
    existing = existing_s3.get(key)
    need_upload = existing is None or (r.get("last_modified") and r["last_modified"] != existing.get("source_last_modified"))
    if need_upload:
        print("Insert" if existing is None else "Update", key)
        inserted += 1 if existing is None else 0
        updated += 0 if existing is None else 1
        resp = session.get(r["url"], timeout=60)
        resp.raise_for_status()
        # Use resp.content so decompression (e.g. gzip) is applied; resp.raw would upload compressed bytes
        body = resp.content
        meta = {"source-last-modified": r["last_modified"]} if r.get("last_modified") else {}
        kwargs = {"Bucket": bucket, "Key": key, "Body": body}
        if meta:
            kwargs["Metadata"] = meta
        # BLS data files have no extension; set CSV type and download filename so they open when downloaded
        base = key.rsplit("/", 1)[-1]
        if ".data." in base or base.endswith("Current") or base.endswith("AllData"):
            kwargs["ContentType"] = "text/csv"
            download_name = base.replace(".", "_") + ".csv"
            kwargs["ContentDisposition"] = f'attachment; filename="{download_name}"'
        s3.put_object(**kwargs)


for key in list(existing_s3.keys()):
    if key not in remote_keys:
        print("Delete", key)
        s3.delete_object(Bucket=bucket, Key=key)
        deleted += 1

print(f"Inserted: {inserted}, Updated: {updated}, Deleted: {deleted}")