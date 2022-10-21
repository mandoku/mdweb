import sys, os, site
os.environ['SECRET_KEY'] = "My very own secret secret"
os.environ['GITHUB_OAUTH_CLIENT_ID'] = "0f110970561b2b2f413f"
os.environ['GITHUB_OAUTH_CLIENT_SECRET'] = "64c0d6b833629afa7aa53b507dc3b31d757743cb"

#site.addsitedir('/Users/Shared/baseline/mdweb/venv/lib/python2.7/site-packages')
site.addsitedir('/Users/chris/.pyenv/versions/venv/lib/python2.7/site-packages')
sys.path.insert(0, '/Users/Shared/baseline/mdweb')
from manage import app

if __name__ == "__main__":
    app.run()
