import logging
from django.shortcuts import HttpResponseRedirect

logger = logging.getLogger(__name__)

def index(request):
    logger.info(f"User: {request.user}")
    return HttpResponseRedirect('/session/')
