python setup.py sdist
rm -r MIRDCalculator.egg-info
mv dist/* .
rm -r dist/
pip install MIRDCalculator-2.4.1.tar.gz
