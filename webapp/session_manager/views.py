import logging
from django.http import HttpResponse
from django.conf import settings


logger = logging.getLogger(__name__)


def index(request):
    logger.info(f'CTRL_HOST: {settings.CTRL_HOST}')
    return HttpResponse("Hello, world. You're at the session index.")
