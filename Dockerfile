FROM registry-app.eng.qops.net:5001/base/python:2.7-onbuild

#Set the working directory to /feeding_frenzy
WORKDIR /feeding_frenzy

#Copy our script into the container
ADD feeding_frenzy.py /feeding_frenzy
ADD requirements.txt /feeding_frenzy

# FOR NOW, FIX LATER
# Add google calendar credentials
ADD google-calendar-cred.json /feeding_frenzy

# Install needed packages
RUN pip install -r requirements.txt

# Run feeding_frenzy.py when container launches
CMD ["python", "feeding_frenzy.py"]


