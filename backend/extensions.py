from flask_caching import Cache

# Shared Cache instance — initialised in create_app() via cache.init_app(app).
# Import this from any blueprint to use caching decorators.
cache = Cache()
