#!/usr/bin/python
# -*- coding: UTF-8 -*-
import pymysql
import base64
import json
import requests
import os.path
import sys


PY2 = sys.version_info[0] == 2

color_for_hard = [0, 255, 0, 128]
color_for_soft = [70, 130, 180, 255]
color_for_hemo = [255, 0, 0, 128]
color_for_micr = [255, 0, 255, 255]


class LabelFileError(Exception):
    pass


class LabelFile(object):
    suffix = '.json'
    to_chi = {'hard': '硬性渗出', 'soft': '软性渗出', 'hemorrhage': '视网膜出血', 'microaneurysms': '微血管瘤',
              'none': '糖网1级', 'mild': '糖网2级', 'moderate': '糖网3级', 'severe': '糖网4级', 'proliferative':
              '糖网5级', 'dme0': '黄斑水肿0级', 'dme1': '黄斑水肿1级', 'dme2': '黄斑水肿2级'}

    to_eng = {'硬性渗出': 'hard', '软性渗出': 'soft', '视网膜出血': 'hemorrhage','微血管瘤': 'microaneurysms',
              '糖网1级': 'none', '糖网2级': 'mild', '糖网3级': 'moderate', '糖网4级': 'severe',
              '糖网5级': 'proliferative', '黄斑水肿0级': 'dme0', '黄斑水肿1级': 'dme1', '黄斑水肿2级': 'dme2'}

    def __init__(self, filename=None, data=None):
        self.cloud_config = json.load(open('config.json', 'r'))
        self.shapes = ()
        self.imagePath = None
        self.imageData = None
        if filename is not None:
            try:
                with open(filename, 'rb' if PY2 else 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    print('get data from filename')
                    self.load(data)
                    self.filename = filename
            except Exception as e:
                raise LabelFileError(e)
        elif data is not None:
            self.load(data)
            self.filename = None
        else:
            self.filename = None

    def load(self, data):
        keys = [
            'imageData',
            'imagePath',
            'lineColor',
            'fillColor',
            'shapes',  # polygonal annotations
            'flags',   # image level flags
        ]
        # try:
            # if data['imageData'] is not None:
            #     imageData = base64.b64decode(data['imageData'])
            # else:
                # relative path from label file to relative path from cwd

            # imagePath = os.path.join(os.path.dirname(filename),
            #                          data['imagePath'])
            # with open(imagePath, 'rb') as f:
            #     imageData = f.read()

        flags = data.get('flags')
        # print('get flags from data')
        flags_chi = {}
        for key in flags:
            if key in self.to_chi:
                flags_chi[self.to_chi[key]] = flags[key]
            else:
                flags_chi[key] = flags[key]

        imagePath = data['imgPath']
        lineColor = [255, 255, 255, 128]
        fillColor = [255, 255, 255, 128]
        shapes = data['shapes']

        for shape in shapes:
            if shape['label'] in self.to_chi:
                shape['label'] = self.to_chi[shape['label']]

            if shape['label'] == '硬性渗出':
                shape['line_color'] = color_for_hard
            elif shape['label'] == '软性渗出':
                shape['line_color'] = color_for_soft
            elif shape['label'] == '视网膜出血':
                shape['line_color'] = color_for_hemo
            elif shape['label'] == '微血管瘤':
                shape['line_color'] = color_for_micr
            else:
                shape['line_color'] = [255, 255, 255, 128]

            shape['fill_color'] = [255, 255, 255, 128]
        # print('english to chinese')
        shapes_chi = (
            (s['label'], s['points'], s['line_color'], s['fill_color'])
            for s in shapes
        )

        # except Exception as e:
        #     raise LabelFileError(e)

        otherData = {}
        for key, value in data.items():
            if key not in keys:
                otherData[key] = value

        # Only replace data after everything is loaded.
        self.flags = flags_chi
        self.shapes = shapes_chi
        self.imagePath = imagePath
        # self.imageData = imageData
        self.lineColor = lineColor
        self.fillColor = fillColor
        # self.filename = filename
        self.otherData = otherData

    def save(self, filename, shapes, imagePath, imageData=None,
             lineColor=None, fillColor=None, otherData=None,
             flags=None):
        # if imageData is not None:
        #     imageData = base64.b64encode(imageData).decode('utf-8')
        token = self.cloud_config['token']
        cloud_save_ip = self.cloud_config['cloud_save_ip']
        database_ip = self.cloud_config['database_ip']
        db_name = self.cloud_config['db_name']
        username = self.cloud_config['username']
        password = self.cloud_config['password']

        if otherData is None:
            otherData = {}
        if flags is None:
            flags_eng = {}
        else:
            flags_eng = {}
            for key in flags:
                if key in self.to_eng:
                    flags_eng[self.to_eng[key]] = flags[key]
                else:
                    flags_eng[key] = flags[key]
        for shape in shapes:
            if shape['label'] in self.to_eng:
                shape['label'] = self.to_eng[shape['label']]

        data = dict(
            flags=flags_eng,
            shapes=shapes,
            # lineColor=lineColor,
            # fillColor=fillColor,
            imgPath=imagePath,
            # imageData=imageData,
        )
        for key, value in otherData.items():
            data[key] = value
        try:
            print('other data:', otherData)
            print('data.imgPath:', data['imgPath'])
            with open(filename, 'wb' if PY2 else 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.filename = filename
            data = {"token": token}
            files = {
                "img": open(filename, "rb")
            }
            r = requests.post(cloud_save_ip, data, files=files)
            print(r.text)
            result = json.loads(r.text)
            if result.get('status') == 200:
                print("json_path",result.get('img_path'))
                filename = result.get('img_path')
            else:
                print('error')

        except Exception as e:
            print(e)
            raise LabelFileError(e)
# 写到数据库
        db = pymysql.connect(database_ip, username, password, db_name, charset='utf8')
        #db = pymysql.connect("localhost", "root", "hejiawen", "label", charset='utf8')
        cursor = db.cursor()
        cursor.execute("SELECT VERSION()")      # 测试是否连上数据库-----------------------------------
        data = cursor.fetchone()
        print("Database version : %s " % data)

        if flags['糖网1级'] == True:
            retino_grade = 1
        elif flags['糖网2级'] == True:
            retino_grade = 2
        elif flags['糖网3级'] == True:
            retino_grade = 3
        elif flags['糖网4级'] == True:
            retino_grade = 4
        elif flags['糖网5级'] == True:
            retino_grade = 5
        else:
            retino_grade = -1

        if flags['黄斑水肿0级'] == True:
            dme = 0
        elif flags['黄斑水肿1级'] == True:
            dme = 1
        elif flags['黄斑水肿2级'] == True:
            dme = 2
        else:
            dme = -1

        flags = json.dumps(flags_eng)
        shapes = json.dumps(shapes)

        name = imagePath.split('/')[-1]
        # if name == '':
        #     name = imagePath1.split('/')[-1]

        print("db test:")
        print(name, imagePath)

        # try:
        #     data = {"token": token}
        #     files = {
        #         "img": open(imagePath1, "rb")
        #     }
        #     r = requests.post(cloud_save_ip, data, files=files)
        #     print(r.text)
        #     result = json.loads(r.text)
        #     if result.get('status') == 200:
        #         print("img_path", result.get('img_path'))
        #         imagePath1 = result.get('img_path')
        #     else:
        #         print('error')
        # except Exception as e:
        #     print(e)

        sql = 'SELECT EXISTS(SELECT 1 FROM label_info WHERE name=%(name)s)'
        value = {
            'name': name
        }
        cursor.execute(sql, value)
        ret = cursor.fetchall()[0]
        if ret[0] == 1:
            #已经存在了，更新
            print('已经存在，准备更新')
            sql = "UPDATE label_info set img_path = %(img_path)s, json_path = %(json_path)s,flags = %(flags)s,shapes = %(shapes)s,retino_grade = %(retino_grade)s,dme = %(dme)s where name = '"+ str(name)+"'"

            value = {
                'img_path': imagePath,
                'json_path': filename,
                'flags': flags,
                'shapes': shapes,
                'retino_grade': retino_grade,
                'dme': dme,

            }
            print("ready to update")
            try:
                cursor.execute(sql, value)
                db.commit()
                print('yes')
            except Exception as e:
                print(e, "update error!")
                db.rollback()
        else:
            print('准备插入')
            sql = "INSERT INTO label_info(name, img_path, json_path, flags, shapes, retino_grade, dme)\
                  VALUES ('%s', '%s', '%s', '%s', '%s', '%s', '%s')" % (name, imagePath, filename, flags, shapes, retino_grade, dme)
            print("ready to insert")
            try:
                cursor.execute(sql)
                db.commit()
            except Exception as e:
                print(e, "insert error!")
                db.rollback()
        db.close()

    @staticmethod
    def isLabelFile(filename):
        return os.path.splitext(filename)[1].lower() == LabelFile.suffix
