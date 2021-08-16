import ftplib
import re
import sys
import os
import json
import pymysql
import socket
import base64
import random
import io
from tenacity import *
from uuid import uuid4
from flask import Flask, request, flash, redirect, url_for, send_file
from werkzeug.datastructures import FileStorage
from functools import wraps
from flask_restful import reqparse, abort, Api, Resource
from datetime import timedelta, datetime
from pytz import timezone
import time
import logging
from threading import Lock
from ftplib import FTP

app = Flask(__name__)

api = Api(app)
parser = reqparse.RequestParser()


def NowTime():
	return datetime.now(timezone('Asia/Taipei')).strftime("%Y-%m-%d %H:%M:%S")


def after_request(response):
	response.headers['Access-Control-Allow-Origin'] = '*'
	response.headers['Access-Control-Allow-Methods'] = 'PUT,GET,PATCH,DELETE,POST'
	response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization,Referrer-Policy'

	return response


app.after_request(after_request)
app.config['PROPAGATE_EXCEPTIONS'] = True

class ftpfunc():
	def connect(self):
		ftp = FTP('gdlab-dev.local')
		ftp.login('GDLab','8TRcrZ')
		ftp.cwd('img')
		return ftp
	
	def upload(self, file, id):
		ftp = self.connect()
		ftp.storbinary("STOR "+id,file,1024)
		ftp.quit()

	def download(self, file, id):
		ftp = self.connect()
		try:
			ftp.retrbinary("RETR "+id+".jpg",file.write)
		except:
			ftp.quit()
			return False
		ftp.quit()

	
class ConnectionManager(object):
	__instance = None
	__connection = None
	__lock = Lock()

	def __new__(cls):
		if ConnectionManager.__instance is None:
			ConnectionManager.__instance = object.__new__(cls)
		return ConnectionManager.__instance

	def __getConnection(self):
		if (self.__connection == None):
			db_settings = {
				"host": "gdlab-dev.local",
				"port": 3306,
				"user": "clec",
				"password": "jCLP4x",
				"db": "inventory",
				"charset": "utf8"
			}
		self.__connection = pymysql.connect(**db_settings)
		return self.__connection

	def __removeConnection(self):
		self.__connection = None

	@retry(stop=stop_after_attempt(3), wait=wait_fixed(10), retry=retry_if_exception_type(pymysql.Error), after=after_log(app.logger, logging.DEBUG))
	def executeQueryJSON(self, procedure, payload=None):
		result = {}
		try:
			conn = self.__getConnection()

			cursor = conn.cursor()

			if payload:
				cursor.execute(f"CALL {procedure}(%s)", json.dumps(payload))
			else:
				cursor.execute(f"CALL {procedure}()")

			raw = ''
			for r in cursor.fetchall():
				for inr in r:
					raw = raw + inr
			result = json.loads(raw)
			print(result)
		except pymysql.Error as e:
			if isinstance(e, pymysql.ProgrammingError) or isinstance(e, pymysql.OperationalError):
				app.logger.error(f"{e.args[1]}")
				if e.args[0] == "08S01":
					
					self.__removeConnection()
					raise
		finally:
			conn.commit()
			cursor.close()
			self.__removeConnection()
		return result


class Queryable(Resource):
	def executeQueryJson(self, verb, payload=None):
		entity = type(self).__name__.lower()
		procedure = f"web.`{verb}_{entity}`"
		print(procedure)
		result = ConnectionManager().executeQueryJSON(procedure, payload)
		return result

@app.route('/')
def index():
	return "Hello"

class Login(Queryable):
	def post(self):
		parser.add_argument('Account')
		parser.add_argument('Passwd')
		args = parser.parse_args()
		try:
			result = self.executeQueryJson("post", args)
		except:
			result = json.dumps({'message':'incorrect username or password'})
		return result, 200

class Object(Queryable,ftpfunc):
	def get(self, multi):
		args = {}
		args['id'] = multi
		result = self.executeQueryJson("get", args)
		return result, 200

	def post(self, multi = None):
		result = {}
		if multi == None:
			parser.add_argument('id')
			parser.add_argument('year')
			parser.add_argument('appellation')
			parser.add_argument('buydate')
			parser.add_argument('source')
			parser.add_argument('unit')
			parser.add_argument('keeper')
			parser.add_argument('note')
			args = parser.parse_args()
			args['status'] = 'in stock'
			if args['note'] == None:
				args['note'] = ''
			result = self.executeQueryJson("post", args)
			
		elif multi == 'multi':
			parser.add_argument('args',type = dict,action="append")
			args = parser.parse_args()['args']
			result = []
			for i in args:
				i['status'] = 'in stock'
				if i['note'] == None:
					i['note'] = ''
				result.append(self.executeQueryJson("post", i))
		return result, 200

	def delete(self):
		parser.add_argument('id')
		args = parser.parse_args()
		result = self.executeQueryJson("delete", args)
		return result, 200
	
	def patch(self):
		parser.add_argument('args',type = dict)
		args = parser.parse_args()['args']
		print(args)
		result = self.executeQueryJson("patch", args)
		return result, 200

class Borrow(Queryable):
	def get(self, id):
		args = {}
		args['id'] = id
		result = self.executeQueryJson("get", args)
		return result, 200

	def post(self):
		parser.add_argument('args',type = dict,action="append")
		args = parser.parse_args()['args']
		print(args)
		result = []
		for i in args:
			result.append(self.executeQueryJson("post", i))
		return result, 200

class Borrowing(Queryable):
	def get(self):
		result = self.executeQueryJson("get")
		return result, 200

class Return(Queryable):
	def get(self, id):
		args = {}
		args['id'] = id
		result = self.executeQueryJson("get", args)
		return result, 200

	def post(self):
		parser.add_argument('args',type = dict,action="append")
		args = parser.parse_args()['args']
		result = []
		for i in args:
			result.append(self.executeQueryJson("post", i))
		return result, 200

class Objects(Queryable):
	def get(self, type = None):
		result = {}
		if type == None:
			result = self.executeQueryJson("get")
		elif type == 'instock':
			result = self.executeQueryJson("get_instock")
		return result, 200

class Img(Queryable ,ftpfunc):
	def post(self, id):
		parser.add_argument('image', type=FileStorage, location='files')
		args = parser.parse_args()
		imgpath = id+'.jpg'
		img = args['image'].save(imgpath)
		del img
		file = open(imgpath,'rb')
		self.upload(file,imgpath)
		os.remove(imgpath)
		return send_file(io.BytesIO(file.read()),mimetype='image/jpeg',as_attachment=True,download_name='%s.jpg' % id)
	def get(self, id):
		file = open('file.jpg', 'wb')
		img = self.download(file, id)
		if img == False:
			return {"message":"no image"}, 200
		else:
			file.close()
			file = open('file.jpg', 'rb')
			os.remove('file.jpg')
			return send_file(io.BytesIO(file.read()),mimetype='image/jpeg',as_attachment=True,download_name='%s.jpg' % id)

class Search(Queryable):
	def get(self, keyword):
		key = keyword.split(',')
		result = []
		for i in key:
			args = {}
			args['keyword'] = i
			temp = self.executeQueryJson("get", args)
			for t in temp:
				if t in result:
					result.append(t)
		return result, 200

class History(Queryable):
	def get(self, id):
		args = {}
		args['id'] = id
		result = self.executeQueryJson("get", args)
		return result, 200

api.add_resource(Login, '/login')
api.add_resource(Object, '/object','/object/<multi>')
api.add_resource(Objects, '/objects','/objects/<type>')
api.add_resource(Borrow, '/borrow', '/borrow/<id>')
api.add_resource(Borrowing, '/borrowing')
api.add_resource(Return, '/return')
api.add_resource(Img, '/img/<id>')
api.add_resource(Search, '/search/<keyword>')
api.add_resource(History, '/history/<id>')

if __name__ == '__main__':
	app.run(host='0.0.0.0', port=80)
