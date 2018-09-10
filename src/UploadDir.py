#-*- coding:utf-8 -*-
from baidupcsapi import PCS
import progressbar
import os
import json
import time
   
'''
作用：将该文件复制到指定目录下，上传当前所在目录下某个文件夹下的所有文件到百度云盘，若云盘上存在某个文件，则跳过
用法：见__main__函数
依赖：python3.6
      baidupcsapi（可用pip安装，但有bug需要自己改动，可去github下载最新版）
      progressbar 

'''

class ProgressBar():
    def __init__(self):
        self.first_call = True

    def __call__(self, *args, **kwargs):
        if self.first_call:
            self.widgets = [progressbar.Percentage(), ' ', progressbar.Bar(marker=progressbar.RotatingMarker('>')),' ', progressbar.ETA()]
            self.pbar = progressbar.ProgressBar(widgets=self.widgets, maxval=kwargs['size']).start()
            self.first_call = False

        if kwargs['size'] <= kwargs['progress']:
            self.pbar.finish()
        else:
            self.pbar.update(kwargs['progress'])



class BaiduCloud(object):
    def __init__(self, username, password):
        if not username or not password:
            print('[ERROR]:username or password cannot be empty')
        self.pcs = PCS(username, password)
        self.local_dict = {}
        self.remote_dict = {}


    def getRemoteDict(self, path):
        self.remote_dict = {}
        if self._getRemoteDict(path, self.remote_dict):
            return self.remote_dict
        else:
            return None
    

    def _getRemoteDict(self, path, ret):
        d = eval(self.pcs.list_files(path).content)
        if d['errno'] != 0 :
            if d['errno'] != -9:
                print('[ERROR]:%s'%(d))
                return False
            else:
                print('[ERROR]:get remote directory %s fails, is it empty?'%(path))
                return False
        l = [(os.path.join(path, entry['server_filename']),entry['isdir']) 
                for entry in d['list'] ]
        ret.setdefault(path, [i[0] for i in l if i[1]==0])
        for i in l:
            if i[1] == 1:
                if(False == self._getRemoteDict(i[0], ret)):
                    return False

        return True


    def getLocalDict(self, path):
        self.local_dict = {}
        self._getLocalDict(path, self.local_dict)
        return self.local_dict


    def _getLocalDict(self, path, ret):
        children = os.listdir(path)
        children = [os.path.join(path, child) 
                for child in children if not os.path.isdir(child)]
        ret.setdefault(path, children)
        for child in children:
            if os.path.isdir(child):
                self._getLocalDict(child, ret)


    def getUploadFileList(self):
        filelist = []
        for dir_entry in self.local_dict:
            for file_entry in self.local_dict[dir_entry]:
                if not ('/'+dir_entry) in self.remote_dict or not ('/'+file_entry) in self.remote_dict['/'+dir_entry]:
                    if not os.path.isdir(file_entry):
                        filelist.append(file_entry)
        return filelist


    def isLegalName(self, path_file):
        characterset = ['\r', '\n', '*', '<', '\\', ':', '?', '"']
        filename = os.path.basename(path_file)
        for c in characterset:
            if c in filename:
                return False
        return True

    
    def _upload_file(self, local_file, remote_path):
        '''
        local_file:文件名，相对路径
        remote_path:/自动备份文件夹
        '''
        #using big file upload interface
        block_size = 10 * 1000 * 1000
        def isBigFile(f):
            if os.path.getsize(f) >= block_size: 
                return True
            return False

        md5list = []
        if not os.path.exists(local_file): 
            print('[ERROR]:file not exist')
            return False

        if not self.isLegalName(local_file):
            print('[ERROR]:filename is illegal')
            return False

        if isBigFile(local_file):
            f = open(local_file,'rb')
            count = 0
            while(True):
                print('big file:uploading %s:part%s'%(local_file,count))
                count = count + 1
                data = f.read(block_size)
                if len(data) == 0:
                    break
                with open(local_file+'_temp', 'wb') as tmpf:
                    tmpf.write(data)
                ret = self.pcs.upload_tmpfile(open(local_file+'_temp','rb'), callback=ProgressBar())
                os.remove(local_file+'_temp')
                md5list.append(json.loads(ret.content)['md5'])
            f.close()        
            ret = self.pcs.upload_superfile(os.path.join(remote_path, os.path.basename(local_file)), md5list)
            return ret 
        else:
            with open(local_file,'rb') as f:
                ret = self.pcs.upload_tmpfile(f, callback=ProgressBar())
                md5list.append(json.loads(ret.content)['md5'])
                ret = self.pcs.upload_superfile(
                        os.path.join(remote_path,os.path.basename(local_file)), md5list)
                return ret
    

    def uploadDirectory(self, local_dir):
        print('=======local files==========')
        print(self.getLocalDict(local_dir))
        print('\n=====remote files===========')
        ret = self.getRemoteDict('/'+local_dir)
        if ret == None:
            print('[]')
            list_file_to_upload = [ f for entry in self.local_dict 
                    for f in self.local_dict[entry] if not os.path.isdir(f)]
        else:
            print(ret)
            list_file_to_upload = self.getUploadFileList()
        print('\n=====to upload===========')
        print(list_file_to_upload)

        print('\n=====start to upload=======')
        for i in range(len(list_file_to_upload)):
            entry = list_file_to_upload[i]
            if '_temp' in os.path.basename(entry):
                print('file:%s is tmp file, skip'%(entry))
                continue
            print('[%s/%s]:upload file: %s'%(i, len(list_file_to_upload),entry))
            ret = self._upload_file(entry, '/'+os.path.dirname(entry))
            if ret :
                print(('OK' if ret.status_code == 200 else 'ERROR'))
            else:
                print(ret)
            time.sleep(0.5)
            
                


if __name__ == '__main__':
    #change the usename and password here
    username = ''
    password = ''

    choice = None
    finished = False
    dirs = [f for f in os.listdir('.') if os.path.isdir(f)] 
    for i in range(0, len(dirs)):
        print('%s : %s'%(i, dirs[i]))
    print('choose the directory you want to upload')
    choice = int(input('number:'))
    
    while(finished == False):
        try:
            baidu = BaiduCloud(username,password)
            if choice in range(len(dirs)):
                baidu.uploadDirectory(dirs[choice])
            finished = True
        except BaseException as e:
            finished = False
            print('Exception occurs:' + str(e))
            time.sleep(10)
    print('all files haved been uploaded!')


#    print(baidu.getRemoteDict('/自动备份文件夹'))

