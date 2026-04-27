import logging
from django.shortcuts import HttpResponseRedirect


logger = logging.getLogger(__name__)


def index(request):
    logger.info(f"User: {request.user}")

    if request.user.is_authenticated:
        return HttpResponseRedirect("janus/session/")

    return HttpResponseRedirect("authentication/signup/")
