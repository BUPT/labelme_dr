基于Labelme开发的眼底影像标注系统
开发者：chaiwenjun000、Suzakue


该系统的主要功能：
1. 为眼底影像选取病变等级。目前支持的有：糖尿病视网膜病变（5个级别）、黄斑水肿病变（3个级别）
2. 在眼底影像上勾画并发症区域，并选择并发症标签。目前支持的并发症有：硬性渗出、软性渗出、微血管瘤、视网膜出血
3. 不同的并发症区域显示为不同的线条颜色
4. 支持模型预标注：先将图片通过深度学习模型得到结果，在这个结果的基础上进行修改
5. 云端存储：支持将标注的图片、标注的信息以及生成的json文件存储到云端mysql数据库


使用方法：
1. 在labelme文件夹下新建config.json文件，内容包括：

   1）"pre_label_ip": 申请模型预标注的ip地址（将眼底图像发送到该地址，服务器运行模型后会返回预标注json）
   
   2）"get_img_ip": 申请裁剪后图片的ip地址（模型预处理时会对图片进行裁剪，我们需要展示裁剪后的图片，否则病症区域的坐标无法与眼底图片一一对应）
   
   3）"token": 5566, 口令字段（通过该字段与服务器进行交互）
   
   4）"cloud_save_ip": 申请云端存储的ip地址（通过该地址将标注后生成的json文件存储到云端）
   
   5）"database_ip": 云端mysql数据库的ip地址
   
   6）"db_name": 云端数据库的名字 
   
   7）"username": 数据库登录名
   
   8）"password": 数据库登陆密码
   
2. 若要修改病变级别标签，请修改labelme/flags.txt；若要修改并发症标签，请修改labelme/labels.txt。但对于新增加的字段不支持中英文转化功能。（为贴合模型预处理的结果，我们把json文件设计为英文标签，页面仍然显示中文标签。若新加标签，json文件内将输出该标签的中文形式）
3. 在labelme文件夹下，运行python main.py命令


以下为原版labelme标注系统的说明：
-----------------------------------------------------------

<img src="https://github.com/wkentaro/labelme/blob/master/labelme/icons/icon.png?raw=true" align="right" />

# labelme: Image Polygonal Annotation with Python

[![PyPI Version](https://img.shields.io/pypi/v/labelme.svg)](https://pypi.python.org/pypi/labelme)
[![Python Versions](https://img.shields.io/pypi/pyversions/labelme.svg)](https://pypi.org/project/labelme)
[![Travis Build Status](https://travis-ci.org/wkentaro/labelme.svg?branch=master)](https://travis-ci.org/wkentaro/labelme)
[![Docker Build Status](https://img.shields.io/docker/build/wkentaro/labelme.svg)](https://hub.docker.com/r/wkentaro/labelme)


Labelme is a graphical image annotation tool inspired by <http://labelme.csail.mit.edu>.  
It is written in Python and uses Qt for its graphical interface.

<img src="https://github.com/wkentaro/labelme/blob/master/examples/instance_segmentation/.readme/annotation.jpg?raw=true" width="80%" />
<i>Fig 1. Annotation example of instance segmentation.</i>

<img src="https://github.com/wkentaro/labelme/blob/master/examples/instance_segmentation/data_dataset_voc/JPEGImages/2011_000006.jpg?raw=true" width="19%" /> <img src="https://github.com/wkentaro/labelme/blob/master/examples/instance_segmentation/data_dataset_voc/SegmentationClassPNG/2011_000006.png?raw=true" width="19%" /> <img src="https://github.com/wkentaro/labelme/blob/master/examples/instance_segmentation/data_dataset_voc/SegmentationClassVisualization/2011_000006.jpg?raw=true" width="19%" /> <img src="https://github.com/wkentaro/labelme/blob/master/examples/instance_segmentation/data_dataset_voc/SegmentationObjectPNG/2011_000006.png?raw=true" width="19%" /> <img src="https://github.com/wkentaro/labelme/blob/master/examples/instance_segmentation/data_dataset_voc/SegmentationObjectVisualization/2011_000006.jpg?raw=true" width="19%" />  
<i>Fig 2. VOC dataset example of instance segmentation.</i>

<img src="https://github.com/wkentaro/labelme/raw/master/examples/semantic_segmentation/.readme/annotation.jpg?raw=true" width="30%" /> <img src="https://github.com/wkentaro/labelme/blob/master/examples/bbox_detection/.readme/annotation.jpg?raw=true" width="32%" /> <img src="https://github.com/wkentaro/labelme/blob/master/examples/classification/.readme/annotation_cat.jpg?raw=true" width="33%" />  
<i>Fig 3. Other examples (semantic segmentation, bbox detection, and classification).</i>


## Features

- [x] Image annotation for polygon, rectangle, line and point. ([tutorial](https://github.com/wkentaro/labelme/blob/master/examples/tutorial))
- [x] Image flag annotation for classification and cleaning. ([#166](https://github.com/wkentaro/labelme/pull/166))
- [x] Video annotation. ([video annotation](https://github.com/wkentaro/labelme/blob/master/examples/video_annotation))
- [x] GUI customization (predefined labels / flags, auto-saving, label validation, etc). ([#144](https://github.com/wkentaro/labelme/pull/144))
- [x] Exporting VOC-like dataset for semantic/instance segmentation. ([semantic segmentation](https://github.com/wkentaro/labelme/blob/master/examples/semantic_segmentation), [instance segmentation](https://github.com/wkentaro/labelme/blob/master/examples/instance_segmentation))



## Requirements

- Ubuntu / macOS / Windows
- Python2 / Python3
- [PyQt4 / PyQt5](http://www.riverbankcomputing.co.uk/software/pyqt/intro) / [PySide2](https://wiki.qt.io/PySide2_GettingStarted)


## Installation

There are options:

- Platform agonistic installation: [Anaconda](#anaconda), [Docker](#docker)
- Platform specific installation: [Ubuntu](#ubuntu), [macOS](#macos), [Windows](#windows)

### Anaconda

You need install [Anaconda](https://www.continuum.io/downloads), then run below:

```bash
# python2
conda create --name=labelme python=2.7
source activate labelme
# conda install -c conda-forge pyside2
conda install pyqt
pip install labelme
# if you'd like to use the latest version. run below:
# pip install git+https://github.com/wkentaro/labelme.git

# python3
conda create --name=labelme python=3.6
source activate labelme
# conda install -c conda-forge pyside2
# conda install pyqt
pip install pyqt5  # pyqt5 can be installed via pip on python3
pip install labelme
```

### Docker

You need install [docker](https://www.docker.com), then run below:

```bash
wget https://raw.githubusercontent.com/wkentaro/labelme/master/labelme/cli/on_docker.py -O labelme_on_docker
chmod u+x labelme_on_docker

# Maybe you need http://sourabhbajaj.com/blog/2017/02/07/gui-applications-docker-mac/ on macOS
./labelme_on_docker examples/tutorial/apc2016_obj3.jpg -O examples/tutorial/apc2016_obj3.json
./labelme_on_docker examples/semantic_segmentation/data_annotated
```

### Ubuntu

```bash
# Ubuntu 14.04 / Ubuntu 16.04
# Python2
# sudo apt-get install python-qt4  # PyQt4
sudo apt-get install python-pyqt5  # PyQt5
sudo pip install labelme
# Python3
sudo apt-get install python3-pyqt5  # PyQt5
sudo pip3 install labelme
```

### macOS

```bash
# macOS Sierra
brew install pyqt  # maybe pyqt5
pip install labelme  # both python2/3 should work

# or install standalone executable / app
brew install wkentaro/labelme/labelme
brew cask install wkentaro/labelme/labelme
```

### Windows

Firstly, follow instruction in [Anaconda](#anaconda).

```bash
# Pillow 5 causes dll load error on Windows.
# https://github.com/wkentaro/labelme/pull/174
conda install pillow=4.0.0
```


## Usage

Run `labelme --help` for detail.  
The annotations are saved as a [JSON](http://www.json.org/) file.

```bash
labelme  # just open gui

# tutorial (single image example)
cd examples/tutorial
labelme apc2016_obj3.jpg  # specify image file
labelme apc2016_obj3.jpg -O apc2016_obj3.json  # close window after the save
labelme apc2016_obj3.jpg --nodata  # not include image data but relative image path in JSON file
labelme apc2016_obj3.jpg \
  --labels highland_6539_self_stick_notes,mead_index_cards,kong_air_dog_squeakair_tennis_ball  # specify label list

# semantic segmentation example
cd examples/semantic_segmentation
labelme data_annotated/  # Open directory to annotate all images in it
labelme data_annotated/ --labels labels.txt  # specify label list with a file
```

For more advanced usage, please refer to the examples:

* [Tutorial (Single Image Example)](https://github.com/wkentaro/labelme/blob/master/examples/tutorial)
* [Semantic Segmentation Example](https://github.com/wkentaro/labelme/blob/master/examples/semantic_segmentation)
* [Instance Segmentation Example](https://github.com/wkentaro/labelme/blob/master/examples/instance_segmentation)
* [Video Annotation Example](https://github.com/wkentaro/labelme/blob/master/examples/video_annotation)


## FAQ

- **How to convert JSON file to numpy array?** See [examples/tutorial](https://github.com/wkentaro/labelme/blob/master/examples/tutorial#convert-to-dataset).
- **How to load label PNG file?** See [examples/tutorial](https://github.com/wkentaro/labelme/blob/master/examples/tutorial#how-to-load-label-png-file).
- **How to get annotations for semantic segmentation?** See [examples/semantic_segmentation](https://github.com/wkentaro/labelme/blob/master/examples/semantic_segmentation).
- **How to get annotations for instance segmentation?** See [examples/instance_segmentation](https://github.com/wkentaro/labelme/blob/master/examples/instance_segmentation).


## Screencast

<img src="https://github.com/wkentaro/labelme/blob/master/.readme/screencast.gif?raw=true" width="70%"/>


## Testing

```bash
pip install hacking pytest pytest-qt
flake8 .
pytest -v tests
```


## Developing

```bash
git clone https://github.com/wkentaro/labelme.git
cd labelme

# Install anaconda3 and labelme
curl -L https://github.com/wkentaro/dotfiles/raw/master/local/bin/install_anaconda3.sh | bash -s .
source .anaconda3/bin/activate
pip install -e .
```


## How to build standalone executable

Below shows how to build the standalone executable on macOS, Linux and Windows.  
Also, there are pre-built executables in
[the release section](https://github.com/wkentaro/labelme/releases).

```bash
# Setup conda
conda create --name labelme python==3.6.0
conda activate labelme

# Build the standalone executable
conda install pyqt
pip install .
pip install pyinstaller
pyinstaller labelme.spec
dist/labelme --version
```


## Acknowledgement

This repo is the fork of [mpitid/pylabelme](https://github.com/mpitid/pylabelme),
whose development has already stopped.
