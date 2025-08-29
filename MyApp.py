from flask import Flask, render_template, request, redirect, url_for, flash, send_file
import boto3
from botocore.exceptions import NoCredentialsError, ClientError
import urllib.parse
import io

app = Flask(__name__)
app.secret_key = "secret_key"


# --- Helpers ---
def get_s3_client():
    """Return boto3 S3 client or None if no credentials configured"""
    try:
        return boto3.client("s3")
    except NoCredentialsError:
        return None


def ensure_s3():
    """Check credentials before using S3 in endpoints"""
    s3 = get_s3_client()
    if not s3:
        flash(" AWS credentials not found. Please configure them.")
        return None
    return s3


@app.template_filter("urlencode")
def urlencode_filter(s):
    return urllib.parse.quote_plus(s)


# --- Routes ---
@app.route("/")
def home():
    s3 = ensure_s3()
    if not s3:
        return render_template("home.html", buckets=None)
    try:
        buckets = s3.list_buckets().get("Buckets", [])
        return render_template("home.html", buckets=buckets)
    except (NoCredentialsError, ClientError) as e:
        flash(f" AWS error: {str(e)}")
        return render_template("home.html", buckets=None)


@app.route("/bucket/<bucket>")
def list_objects(bucket):
    s3 = ensure_s3()
    if not s3:
        return redirect(url_for("home"))

    try:
        objects = s3.list_objects_v2(Bucket=bucket)
        contents = objects.get("Contents", [])
        buckets = s3.list_buckets()["Buckets"]
        return render_template(
            "objects.html", bucket=bucket, contents=contents, buckets=buckets
        )
    except (NoCredentialsError, ClientError) as e:
        flash(f" Error accessing bucket: {str(e)}")
        return redirect(url_for("home"))


@app.route("/create_bucket", methods=["POST"])
def create_bucket():
    s3 = ensure_s3()
    if not s3:
        return redirect(url_for("home"))

    bucket_name = request.form["bucket_name"]
    try:
        s3.create_bucket(Bucket=bucket_name)
        flash(f" Bucket '{bucket_name}' created successfully")
    except (NoCredentialsError, ClientError) as e:
        flash(f" Failed to create bucket: {str(e)}")
    return redirect(url_for("home"))


@app.route("/delete_bucket/<bucket>")
def delete_bucket(bucket):
    s3 = ensure_s3()
    if not s3:
        return redirect(url_for("home"))

    try:
        s3.delete_bucket(Bucket=bucket)
        flash(f" Bucket '{bucket}' deleted successfully")
    except (NoCredentialsError, ClientError) as e:
        flash(f" Failed to delete bucket: {str(e)}")
    return redirect(url_for("home"))


@app.route("/upload/<bucket>", methods=["POST"])
def upload_file(bucket):
    s3 = ensure_s3()
    if not s3:
        return redirect(url_for("home"))

    file = request.files["file"]
    if file:
        try:
            s3.upload_fileobj(file, bucket, file.filename)
            flash(f" File '{file.filename}' uploaded successfully")
        except (NoCredentialsError, ClientError) as e:
            flash(f" Upload failed: {str(e)}")
    return redirect(url_for("list_objects", bucket=bucket))


@app.route("/delete_file/<bucket>/<path:key>")
def delete_file(bucket, key):
    s3 = ensure_s3()
    if not s3:
        return redirect(url_for("home"))

    try:
        s3.delete_object(Bucket=bucket, Key=key)
        flash(f" File '{key}' deleted successfully")
    except (NoCredentialsError, ClientError) as e:
        flash(f" Delete failed: {str(e)}")
    return redirect(url_for("list_objects", bucket=bucket))


@app.route("/download_file/<bucket>/<path:key>")
def download_file(bucket, key):
    """Download a file from S3"""
    s3 = ensure_s3()
    if not s3:
        return redirect(url_for("home"))

    try:
        file_obj = io.BytesIO()
        s3.download_fileobj(bucket, key, file_obj)
        file_obj.seek(0)
        return send_file(
            file_obj,
            as_attachment=True,
            download_name=key.split("/")[-1]  # just filename
        )
    except (NoCredentialsError, ClientError) as e:
        flash(f" Download failed: {str(e)}")
        return redirect(url_for("list_objects", bucket=bucket))


@app.route("/copy_file/<bucket>/<path:key>", methods=["POST"])
def copy_file(bucket, key):
    s3 = ensure_s3()
    if not s3:
        return redirect(url_for("home"))

    dest_bucket = request.form["dest_bucket"]
    dest_key = request.form.get("dest_key", key)
    try:
        copy_source = {"Bucket": bucket, "Key": key}
        s3.copy(copy_source, dest_bucket, dest_key)
        flash(f" File '{key}' copied to {dest_bucket}/{dest_key}")
    except (NoCredentialsError, ClientError) as e:
        flash(f" Copy failed: {str(e)}")
    return redirect(url_for("list_objects", bucket=bucket))


@app.route("/move_file/<bucket>/<path:key>", methods=["POST"])
def move_file(bucket, key):
    s3 = ensure_s3()
    if not s3:
        return redirect(url_for("home"))

    dest_bucket = request.form["dest_bucket"]
    dest_key = request.form.get("dest_key", key)
    try:
        copy_source = {"Bucket": bucket, "Key": key}
        s3.copy(copy_source, dest_bucket, dest_key)
        s3.delete_object(Bucket=bucket, Key=key)
        flash(f" File '{key}' moved to {dest_bucket}/{dest_key}")
    except (NoCredentialsError, ClientError) as e:
        flash(f" Move failed: {str(e)}")
    return redirect(url_for("list_objects", bucket=bucket))


@app.route("/create_folder/<bucket>", methods=["POST"])
def create_folder(bucket):
    s3 = ensure_s3()
    if not s3:
        return redirect(url_for("home"))

    folder_name = request.form["folder_name"]
    if not folder_name.endswith("/"):
        folder_name += "/"
    try:
        s3.put_object(Bucket=bucket, Key=folder_name)
        flash(f" Folder '{folder_name}' created in bucket '{bucket}'")
    except (NoCredentialsError, ClientError) as e:
        flash(f" Failed to create folder: {str(e)}")
    return redirect(url_for("list_objects", bucket=bucket))


if __name__ == "__main__":
    app.run(debug=True)
