# 新建通用下载器类
class Downloader:
    def __init__(self, save_path):
        self.save_path = save_path
        
    def download(self, url, filename=None):
        # 统一的下载实现
        pass
        
    def extract(self, file_path):
        # 统一的解压实现
        pass 