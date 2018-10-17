#encode: utf-8
#coding: utf-8
from selenium import webdriver
import selenium.common.exceptions as EX
import selenium.webdriver.common.keys as KEY
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
import ssl

ssl._create_default_https_context=ssl._create_unverified_context

class DownloadOver(Exception):
    def __init__(self, msg):
        Exception.__init__(self,msg)
        self.msg = msg

class DownloadInterrupt(DownloadOver):
    pass

class DownloadContinue(DownloadInterrupt):
    pass

HEADER = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Accept-Language': 'zh-CN,zh;q=0.9',
    'Upgrade-Insecure-Requests': 1,
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/69.0.3497.100 Safari/537.36'
}

DOC_URLs = [
    #"https://wenku.baidu.com/view/fed7bf4217fc700abb68a98271fe910ef02dae7f.html",
    #"https://wenku.baidu.com/view/b89a0b15866fb84ae45c8df7.html?sxts=1539746608081",
    #"https://wenku.baidu.com/view/6ad7c612195f312b3069a58a.html?from=search",
    #"https://wenku.baidu.com/view/605c2251a58da0116c1749fb.html?from=search",
    #"https://wenku.baidu.com/view/16e4308e64ce0508763231126edb6f1aff007187.html?from=search",
    #"https://wenku.baidu.com/view/718df9e80408763231126edb6f1aff00bed57031.html?from=search",
    #"https://wenku.baidu.com/view/0dba4967b5daa58da0116c175f0e7cd1842518b0.html?from=search",
    "https://wenku.baidu.com/view/202b4ae3d5bbfd0a7856730b.html?from=search",
    "https://wenku.baidu.com/view/631c04be65ce05087632136b.html?from=search",
    "https://wenku.baidu.com/view/90a5392b5901020207409c6a.html?sxts=1539747189936",
    "https://wenku.baidu.com/view/4f29c2e54afe04a1b071de6a.html?sxts=1539747193351",
    "https://wenku.baidu.com/view/4cd9f274a26925c52cc5bf6a.html?rec_flag=default&sxts=1539747229269",
    "https://wenku.baidu.com/view/16322e9d112de2bd960590c69ec3d5bbfd0ada29.html?from=search",
    "https://wenku.baidu.com/view/dcf1177a657d27284b73f242336c1eb91a37339f.html?from=search",
    "https://wenku.baidu.com/view/afc1e97cf011f18583d049649b6648d7c1c70895.html?from=search",
    "https://wenku.baidu.com/view/9f711a0f178884868762caaedd3383c4bb4cb48e.html?rec_flag=default&sxts=1539747353325",
    "https://wenku.baidu.com/view/d434e620647d27284b7351c2.html?rec_flag=default&sxts=1539747377870",
    "https://wenku.baidu.com/view/e8062129302b3169a45177232f60ddccdb38e617.html?rec_flag=default&sxts=1539747379990",
    "https://wenku.baidu.com/view/a12ea978f02d2af90242a8956bec0975f565a416.html?rec_flag=default&sxts=1539747439689",
    "https://wenku.baidu.com/view/6b4b4d19cd7931b765ce0508763231126edb776b.html?rec_flag=default&sxts=1539747455032",
    "https://wenku.baidu.com/view/03d9e9a8d1d233d4b14e852458fb770bf78a3b3c.html?rec_flag=default&sxts=1539747458009"
]

class WenKu(object):
    def __init__(self, savedir=None):
        init()
        self._browser = webdriver.Chrome()
        self._currentName=''
        self._currentType=''
        self._currentCount=0
        self._page=''
        self._doc_pages=[]

    # void 注入JQuery
    def _InjectJQuery(self):
        '''
        CDN 必须是 HTTPS 的，
        因为百度文库是 HTTPS的，
        如果使用 HTTP 的 CDN，
        那么就会形成混合内容，
        有些浏览器(Chrome)会考虑到安全的问题，从而阻止网站从 CDN 加载 JQuery，
        也就是说，即使成功注入JQuery，也不会加载JQuery
        '''
        fl = open('./injectJQuery.js','r',encoding='utf8')
        script = fl.read()
        fl.close()
        self._browser.execute_script(script)

    # void 访问文档主页
    def GetDocIndex(self, url):
        self._browser.get(url)
        self._InjectJQuery()
        time.sleep(5)

    # void 获取文档标题及类型
    def GetDocNameType(self):
        type_cpath = 'h1.reader_ab_test b.ic'
        types = self._browser.find_element_by_css_selector(type_cpath)
        self._currentName = self._browser.title.encode('utf-8').decode('utf-8')
        classes = types.get_attribute('class')
        types = classes.split(" ")
        for one in types:
            if one.startswith('ic-'):
                self._currentType = one.replace('ic-', "")
                break
        print(f'1: "{self._currentName}"')
        print(f'2: "{self._currentType}"')
    
    # void 获取文档页数
    def GetDocCount(self):
        span = self._browser.find_element_by_css_selector('span.page-count')
        cstr = span.text
        self._currentCount = int(cstr[1:])
        print(f'3: {self._currentCount}')

    # void 根据文档名创建目录
    def MakeDir(self):
        path = pathlib.Path(f'./{self._currentName}')
        if not path.exists():
            pathlib.os.mkdir(f'./{self._currentName}')

    # void 将所有文档加载出来
    def LoadMore(self):
        try:
            go_more = self._browser.find_element_by_css_selector('div#html-reader-go-more')
        except:
            return
        self._browser.execute_script("$('html,body').scrollTop($('#html-reader-go-more').offset().top);")        
        moreBtn = go_more.find_element_by_css_selector('span.moreBtn')
        time.sleep(5)
        moreBtn.click()

    # void 跳转到某页
    def GoToPage(self, index):
        page_input = self._browser.find_element_by_css_selector("div.reader-tools-page input.page-input")
        page_input.clear()
        page_input.clear()
        time.sleep(2)
        page_input.send_keys(KEY.Keys.BACKSPACE)
        page_input.send_keys("")
        page_input.send_keys(str(index))
        time.sleep(2)
        page_input.send_keys(KEY.Keys.ENTER)
    
    def PDFURL(self, index):
        uid = f'#pageNo-{index}'
        page = f'{uid} div.reader-pic-item'
        try:
            page = self._browser.find_element_by_css_selector(page)
            style = page.get_attribute('style')
            styles = style.split(';')
            for style in styles:
                style = style.strip()
                if style.startswith('background-image:'):
                    style = style.replace('background-image:','').strip()
                    self._page = style[5:-2]
                    self._doc_pages.append(style[5:-2])
                    return
        except EX.NoSuchElementException:
            page = f'{uid} img.reader-pptstyle'
            page = self._browser.find_element_by_css_selector(page)
            self._page = page.get_attribute('src')
            self._doc_pages.append(page.get_attribute('src'))
    
    def PDFDownload(self, save_name, url):
        data = self._Request(url)
        fl = open(f'./{self._currentName}/{save_name}.png','wb')
        fl.write(data)

    def _Request(self, url):
        req = urllib.request.Request(url=url, headers=HEADER)
        data = urllib.request.urlopen(req).read()
        return data
    
    def Close(self):
        self._browser.close()
        self._browser.quit()

    def Go(self):
        for url in DOC_URLs:
            self.GetDocIndex(url)
            self.GetDocNameType()
            self.GetDocCount()
            self.MakeDir()
            self.LoadMore()
            for index in range(1, self._currentCount+1):
                self.GoToPage(index)
                time.sleep(1)
                self.PDFURL(index)
                self.PDFDownload(index, self._page)
                print(f'{self._currentName} downloaded: {index} of {self._currentCount}')
                


if __name__ == '__main__':
        wenku = WenKu()
        wenku.Go()
        wenku.Close()