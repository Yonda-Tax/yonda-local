import boto3


_api_key = None


def get_secret(aws_session: boto3.Session, secret_name: str) -> str:
    client = aws_session.client(  # type: ignore[reportUnknownMemberType]
        service_name="secretsmanager",
    )

    get_secret_value_response = client.get_secret_value(SecretId=secret_name)

    return get_secret_value_response["SecretString"]