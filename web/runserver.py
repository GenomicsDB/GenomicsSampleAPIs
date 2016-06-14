import os, sys
import config

# works with new virutalenv changes
basePath = os.path.dirname(os.path.dirname(os.path.realpath(sys.argv[0])))
#configFile = os.path.join(basePath, "web/ga4gh.conf")
configFile = os.path.join(basePath, "web/ga4gh_test.conf")
parser = config.ConfigParser.RawConfigParser()
parser.read(configFile)
if parser.has_section('virtualenv'):
    venv = parser.get('virtualenv', 'virtualenv')

if os.getenv('VIRUTAL_ENV') is None:
    activate_this = venv+'/bin/activate_this.py'
    execfile(activate_this, dict(__file__=activate_this))

from ga4gh import create_app
from flask.ext.cors import CORS, cross_origin

config.initConfig("ga4gh_test.conf")

app=create_app(config.LoadedConfig)


cors = CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'

host = app.config.get('HOST', 'localhost')
from ga4gh import views
from ga4gh.views import ga4gh
app.register_blueprint(views.ga4gh)

if __name__ == '__main__':
    app.run(host=host, debug=True)
