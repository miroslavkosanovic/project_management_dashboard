import jwt
import datetime
import os


def generate_jwt(user):
    payload = {
        "id": user.id,  # The ID of the user
        "name": user.name,  # The name of the user
        "role": user.role,  # The role of the user
        "exp": datetime.datetime.utcnow()
        + datetime.timedelta(days=1),  # The expiration time of the JWT
    }

    jwt_token = jwt.encode(payload, os.getenv("JWT_SECRET"), algorithm="HS256")

    return jwt_token
