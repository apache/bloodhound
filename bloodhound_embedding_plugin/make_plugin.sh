#!/bin/bash

deactivate
cd /home/antonia/Documents/gsoc/bloodhound/bloodhound_embedding_plugin
python setup.py bdist_egg
cp ~/Documents/gsoc/bloodhound/bloodhound_embedding_plugin/dist/BloodhoundEmbeddingPlugin-0.1-py2.7.egg /home/antonia/Documents/gsoc/bloodhound/installer/bloodhound/environments/main/plugins
cd /home/antonia/Documents/gsoc/bloodhound/installer
source bloodhound/bin/activate
tracd ./bloodhound/environments/main --port=8000




