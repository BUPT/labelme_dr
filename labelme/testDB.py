#!/usr/bin/python
# -*- coding: UTF-8 -*-
# import pymysql
#
# db = pymysql.connect("111.207.243.71", "drteam", "pcncad819", "label", charset='utf8')
# cursor = db.cursor()
# cursor.execute("SELECT VERSION()")      # 测试是否连上数据库-----------------------------------
# data = cursor.fetchone()
# print("Database version : %s " % data)
# sql = """INSERT INTO employee(FIRST_NAME,
#          LAST_NAME, SEX)
#          VALUES ('Jiawen', 'He', 'F')"""
# try:
#    # 执行sql语句
#    cursor.execute(sql)
#    # 提交到数据库执行
#    db.commit()
# except:
#    # 如果发生错误则回滚
#    db.rollback()
# db.close()

string = "tttt\ttt"
# for a in string:
#     if a == '\\':
#         a = '/'

# list = string.split('\\')
print(string)
# new_str = ""
# for li in list:
#     new_str += li
# print(new_str)

