from user_sessions.middleware import SessionMiddleware as UserSessionsMiddleware
from django.contrib.sessions.middleware import SessionMiddleware as BaseSessionMiddleware


class SessionMiddleware(BaseSessionMiddleware, UserSessionsMiddleware):
    pass
