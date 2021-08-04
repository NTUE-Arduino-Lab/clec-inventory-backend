from ftplib import FTP
import socket
socket.setdefaulttimeout(60)
ftp = FTP('clecdeMac-mini.local')
ftp.login('GDLab','8TRcrZ')
print(ftp.getwelcome())
ftp.cwd('~/img')
file = open('Yuru-Yuri.jpg','rb')
ftp.storbinary('STOR ~/img/Yuru-Yuri.jpg',file,1024)
file.close()
ftp.quit()