# Configure logging
import logging

from supersetapiplus.client import SupersetClient  # noqa

# The library does not configure application logging (no basicConfig); it only avoids the
# "No handlers could be found" warning when the application configures no handler.
logging.getLogger(__name__).addHandler(logging.NullHandler())
