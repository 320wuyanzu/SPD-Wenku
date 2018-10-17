#encode: utf-8
#coding: utf-8
from selenium import webdriver
import selenium.common.exceptions as EX
import urllib
import time
from requests_html import HTML
import re
import pathlib
import os
import sqlite3 as DB
import hashlib as hashlib
import traceback
from colorama import init
from colorama import deinit
from colorama import Fore
import copy
import json

class DownloadOver(Exception):
    def __init__(self, msg):
        Exception.__init__(self,msg)
        self.msg = msg

class DownloadInterrupt(DownloadOver):
    pass

class DownloadContinue(DownloadInterrupt):
    pass

DOC_URLs = [
    "https://wenku.baidu.com/view/fed7bf4217fc700abb68a98271fe910ef02dae7f.html"
]

class WenKu(object):
    def __init__(self, name, savedir=None):
        init()
        self._browser = webdriver.Chrome()
        self._log = time.strftime('./log/%Y%m%d_%H%M%S.log',time.localtime(time.time()))
        user_path = pathlib.Path(self._dir)
        if not user_path.exists():
            pathlib.os.mkdir(self._dir)
        db_path = pathlib.Path(self._db)
        if not db_path.exists():
            db = open(self._db,'wb')
            db.close()
            db = DB.connect(self._db)
            sql = '''CREATE TABLE {0} (
                        name CHAR NOT NULL UNIQUE,
                        sha512 CHAR NOT NULL UNIQUE,
                        meta BINARY NOT NULL UNIQUE,
                        ext CHAR NOT NULL)'''.format(self._table)
            db.cursor().execute(sql)
            db.commit()
            db.close()
        self._loading_refresh_time = 0
        self._to_download_src = ''
        self._first = ''
        self._pre = ''

        self._currentName=''
        self._currentType=''

    def Log(self, what):
        tm = time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(time.time()))
        tmp = "[{0}] [{1}] [{2}个帖子] {3}".format(tm, self._user_id, self._total, what)
        open(self._log,'a',encoding='utf8').write(tmp+'\n')
        tm = Fore.LIGHTCYAN_EX+tm+Fore.RESET
        user = Fore.GREEN+self._user_id+Fore.RESET
        coun = Fore.LIGHTMAGENTA_EX+self._total.strip()+Fore.RESET
        what = what.replace('error',Fore.LIGHTRED_EX+'error'+Fore.RESET)
        what = what.replace('warning',Fore.LIGHTRED_EX+'error'+Fore.RESET)
        what = what.replace('ignore', Fore.LIGHTYELLOW_EX+'ignore'+Fore.RESET)
       
        rstr = r'\d+\.jpg'
        pattern = re.compile(rstr)
        emm = pattern.search(what)
        if emm != None:
            r = emm.group()
            what = what.replace(r,Fore.LIGHTGREEN_EX+r+Fore.RESET)
        
        rstr = r'\d+\.mp4'
        pattern = re.compile(rstr)
        emm = pattern.search(what)
        if emm != None:
            r = emm.group()
            what = what.replace(r,Fore.LIGHTCYAN_EX+r+Fore.RESET)
        
        rstr = r'\d+\/\d+'
        pattern = re.compile(rstr)
        emm = pattern.search(what)
        if emm != None:
            r = emm.group()
            what = what.replace(r,Fore.LIGHTMAGENTA_EX+r+Fore.RESET)

        rstr = r'^<\d+>$'
        pattern = re.compile(rstr)
        emm = pattern.search(what)
        if emm != None:
            r = emm.group().replace('<','').replace('>','')
            what = what.replace(r,'<'+Fore.LIGHTMAGENTA_EX+r+Fore.RESET+'>')
        
        
        tmp = "[{0}] [{1}] [{2}个帖子] {3}".format(tm, user, coun, what)        
        print(tmp)

    # void 访问文档主页
    def GetDocIndex(self, url):
        try:
            self._browser.get(url)
            time.sleep(10)
        except:
            raise DownloadInterrupt('[Get Doc Index] [error] download interrupt\n%s'%traceback.format_exc())

    # void 获取文档标题及类型
    def GetDocNameType(self):
        name_xpath = '/html/head/title'
        type_cpath = 'h1.reader_ab_test b.ic'
        try:
            title = self._browser.find_element_by_xpath(name_xpath)
            types = self._browser.find_element_by_css_selector(type_cpath)
            self._currentName = title.text.encode('gb2312').decode('utf-8')
            classes = types.get_attribute('class')
            self._currentType = classes
            self._total =  text.replace('帖子','').strip()
            self.Log('[step_2] total <%s> 个帖子'%self._total)
        except:
            self.Log('[step_2] [error] %s'%traceback.format_exc())
            raise DownloadInterrupt('[step_2] [error] download interrupt')

    # first_card 寻找第一项
    def step_3(self):
        try:
            cards = self._browser.find_elements_by_css_selector('div[id^="gridItem_"]')
        except EX.NoSuchElementException:
            time.sleep(5)
            self._loading_refresh_time += 1
            if self._loading_refresh_time == 6:
                self.Log('[step_3] [error] can not find any card !!!!')
                raise DownloadInterrupt('[step_3] [error] download interrupt')
            else:
                self.Log('[step_3] [warning] found no card, refreshed <%d> time.....'%self._loading_refresh_time)
                self._browser.refresh()
                self.Log('[step_3] [warning] researching......')
                time.sleep(10)
                self.step_3()
        else:
            pattern = re.compile(r'^gridItem_\d+$')
            for card in cards:
                card_id = card.get_attribute('id')
                if pattern.match(card_id) != None:# 如果该项不是广告
                    self._first = card
                    break
    
    # 开始点击每一项
    def step_4(self):
        try:
            self._first.click() # 点击第一项，弹出modal
            time.sleep(5)
        except:
            raise DownloadInterrupt('[step_4] [error] download interrupt: %s'%traceback.format_exc())
        while True:
            self._current += 1
            href = self._step_4_1_get_href() # 此页面地址
            id_ = href.split('/')[-1] # 提取id
            self._step_4_2_set_elm_to_download(id_) # 设置要下载的资源,mp4和jpg的选择器不同
            src_url = self._to_download_src.get_attribute('src') # 获取元数据真实地址
            ext = src_url.split('.')[-1] # 提取ext
            name = id_+'.'+ext
            downloaded = self._step_4_3_if_download(name) # 根据 name = id.ext 查询数据库，看是否已经下载
            if not downloaded:# 如果查询不到结果，说明还没下载，则下载
                data = self._step_4_4_download(name,src_url)
                self._step_4_5_save_local(name,data) # 保存到本地
                self._step_4_6_save_database(name,ext) # 保存到数据库
                self.Log('[step_4] [{0}/{1}] {2} downloaded'.format(self._current, self._total, name))
            else:
                self.Log('[step_4] [ignore] [{0}/{1}] {2} has been downloaded'.format(self._current,self._total, name))            
            # 如果下载过了或下载完了就点击→键，加载下一项
            try:
                time.sleep(2)
                next_css = '''body > div.ui.page.modals.dimmer.transition.visible.active 
                                   > div > div > div:nth-child(2) > button'''.strip()
                next_button = self._browser.find_element_by_css_selector(next_css)
            except EX.NoSuchElementException:
                raise DownloadInterrupt('[step_4] [error] no next button')
            else:
                css = next_button.get_attribute('style')
                styles = css.split(';')
                value = ''
                for style in styles:
                    style = style.strip()
                    if style.startswith('opacity'):
                        value = style[-1]
                        break
                if value == '1':
                    if self._pre == name:
                        raise DownloadInterrupt('[step_4] [error] load next failed')
                    else:
                        self._pre = name
                        next_button.click()
                else:
                    raise DownloadOver('[step_4] download is overl')
    
    # 寻找此页面地址
    def _step_4_1_get_href(self):
        href_css = '''body > div.ui.page.modals.dimmer.transition.visible.active 
                           > div > div > div:nth-child(3) > div:nth-child(2) 
                           > div.app-shareButtons > div:nth-child(14) > a'''.strip()
        try:
            href_a = self._browser.find_element_by_css_selector(href_css)
        except EX.NoSuchElementException:
            raise DownloadInterrupt('[step_4.1] [error] can not href <a/>')
        return href_a.get_attribute('href')
    # 查找modal当前的资源是jpg还是mp4
    def _step_4_2_set_elm_to_download(self, id_):
        jpg_css_1 = '''body > div.ui.page.modals.dimmer.transition.visible.active 
                            > div > div > div:nth-child(3) > div:nth-child(1) 
                            > div > div > img:nth-child(3)'''.strip()
        jpg_css_2 = '''body > div.ui.page.modals.dimmer.transition.visible.active 
                            > div > div > div > div:nth-child(2) 
                            > div > div > img:nth-child(3)'''.strip()
        mp4_css = '''body > div.ui.page.modals.dimmer.transition.visible.active 
                          > div > div > div:nth-child(3) > div:nth-child(1) > div > video'''.strip()
        try: # 先看看是不是mp4
            time.sleep(2)
            self._to_download_src = self._browser.find_element_by_css_selector(mp4_css)
        except EX.NoSuchElementException:
            try: # 如果不是mp4，再看看是不是jpg
                self._to_download_src = self._browser.find_element_by_css_selector(jpg_css_1)
            except EX.NoSuchElementException:
                self.Log('[step_4.2] [note] JPG CSS 1 selector failed')
                try:
                    self._to_download_src = self._browser.find_element_by_css_selector(jpg_css_2)
                except EX.NoSuchElementException:
                    self.Log('[step_4.2] [note] JPG CSS 2 selector failed')
                    raise DownloadInterrupt('[step_4.2] [error] ID <%s> either not jpg or mp4'%id_)
    # 根据 name = id.ext 查询数据库，看是否已经下载
    def _step_4_3_if_download(self,name):
        sql = 'SELECT name FROM {0} WHERE name="{1}"'.format(self._table, name)
        conn = DB.connect(self._db)
        curs = conn.cursor()
        curs.execute(sql)
        conn.commit()
        resl = curs.fetchall()
        conn.close()
        if len(resl) == 0:
            return False
        else:
            return True
    # 下载
    def _step_4_4_download(self,name,src_url):
        headers = {
            'Host': 'x.gto.cc', 'Connection': 'keep-alive',
            'Referer': 'https://tofo.me/'+self._user_id,
            'Accept-Encoding': 'gzip, deflate, br', 'Accept-Language': 'zh-CN,zh;q=0.9',
            'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/66.0.3359.139 Safari/537.36'
        }
        try:
            self.Log('[step_4.4] start download %s'%name)
            req = urllib.request.Request(url=src_url,headers=headers)
            data = urllib.request.urlopen(req).read()
            return data
        except urllib.error.HTTPError:
            self.Log('[step_4.4] [error] %s'%traceback.format_exc())
            raise DownloadInterrupt('[step_4] [error] HTTPError')
        except urllib.error.URLError:
            self.Log('[step_4.4] [error] %s'%traceback.format_exc())
            raise DownloadInterrupt('[step_4] [error] URLError')
    # 保存到本地
    def _step_4_5_save_local(self,name,data):
        fl = open(self._dir+"/"+name, "wb")
        fl.write(data)
        fl.flush()
        fl.close()
        #self.Log('[step_4.5] %s saved local'%name)
    # 保存到数据库
    def _step_4_6_save_database(self,name,ext):
        data = open(self._dir+'/'+name, 'rb').read()
        sha512 = hashlib.sha3_512(data).hexdigest()
        sql = 'INSERT INTO {0} VALUES (?,?,?,?)'.format(self._table)
        conn = DB.connect(self._db)
        curs = conn.cursor()
        try:
            curs.execute(sql,(name, sha512, data, ext))
            conn.commit()
        except DB.IntegrityError:
            pass
        finally:
            conn.close()
            #self.Log('[step_4.6] %s saved database'%name )

    def Close(self):
        self._browser.close()

    def Go(self):
        try:
            self.step_1()
            self.step_2()
            self.step_3()
            self.step_4()
        except DownloadInterrupt as ex:
            self.Log(ex.msg)
            self._browser.close()            
        except DownloadOver as ex:
            self.Log(ex.msg)
            self._browser.close()

    @staticmethod
    def GetUsers():
        fl = open('./user.json','r',encoding='utf8')
        data = fl.read()
        fl.close()
        user_dict = json.loads(data)
        users = user_dict.keys()
        r = []
        for user in users:
            if user_dict[user] == 0:
                r.append(user)
        return r


if __name__ == '__main__':
    
    users = Tofo.GetUsers()
    for user in users:
        tofo = Tofo(user)
        try:
            tofo.Go()
        except:
            tofo.Log('[error] [main] {0}'.format(traceback.format_exc()))
            tofo.Close()