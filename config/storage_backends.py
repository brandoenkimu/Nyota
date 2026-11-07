from storages.backends.s3 import S3Storage


class SupabasePublicMediaStorage(S3Storage):
    """Public product images and ordinary uploads."""

    bucket_name = "nyota-product-media"
    custom_domain = (
        "itkxnaqsbtumbpenzbdb.supabase.co/"
        "storage/v1/object/public/nyota-product-media"
    )
    location = ""
    default_acl = None
    querystring_auth = False
    file_overwrite = False


class SupabasePrivateVerificationStorage(S3Storage):
    """Private seller verification documents."""

    bucket_name = "nyota-private-verification"
    location = ""
    default_acl = None
    querystring_auth = True
    file_overwrite = False

