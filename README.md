# Tg-download-channel
This repository was created for a script that helps to download photos, videos from Telegram channels.
In the file (requirements.txt) all the necessary libraries
[requirements.txt](requirements.txt)
```shell
pip install -r requirements.txt
```
then there is a block where you need to enter your information to connect to the telegram server on this site you can create and receive data [telegram.auth](https://my.telegram.org/auth).

```hell
API_ID = ‘ID’
API_HASH = ‘HASH’
PHONE = ‘your phone number (with country code)’
```

If you have trouble installing libraries, create a virtual environment
```hell
python -m venv myenv 
```
(myenv is the name of the environment)
next you need to activate 


Linux/MacOS:
```hell
source myenv/bin/activate
```

Windows:
```hell
myenv\Scripts\activate
```
