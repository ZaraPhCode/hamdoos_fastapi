Place your SSL certificate and key in this folder.

Naming expected by deploy/nginx.conf:
- asha-shop.crt
- asha-shop.key

On the server you can use certbot (e.g. certbot certonly --standalone -d asha-shop.ir -d www.asha-shop.ir)
and copy the issued files here, or install certbot's webroot plugin.