"""
    "XFeat: Accelerated Features for Lightweight Image Matching, CVPR 2024."
    https://www.verlab.dcc.ufmg.br/descriptors/xfeat_cvpr24/

"""

import argparse
import os
import sys
import gdown
import urllib.request
import zipfile
import tarfile


def _urlretrieve(url: str, output_path: str, desc: str = ""):
    """使用 urllib 下载文件，Google Drive 链接回退到 gdown。"""
    label = desc or os.path.basename(output_path)
    print(f"Downloading {label}...")
    try:
        urllib.request.urlretrieve(url, output_path)
    except Exception as e:
        if 'drive.google.com' in url:
            print(f"urllib failed ({e}), trying gdown fallback...")
            gdown.download(url, output_path, quiet=False)
        else:
            raise
    print(f"Downloaded: {output_path}")


def download_megadepth_1500(download_dir):
    """下载 MegaDepth-1500 测试集"""
    files = {
        'test_images': 'https://drive.google.com/uc?id=12yKniNWebDHRTCwhBNJmxYMPgqYX3Nhv',
    }

    os.makedirs(download_dir, exist_ok=True)

    for file_name, url in files.items():
        output_path = os.path.join(download_dir, f'{file_name}.tar')
        gdown.download(url, output_path, quiet=False)

        if tarfile.is_tarfile(output_path):
            print(f"Extracting {output_path}...")
            with tarfile.open(output_path, 'r:tar') as tar:
                tar.extractall(path=download_dir)
            os.remove(output_path)


def download_scannet_1500(download_dir):
    """下载 ScanNet-1500 测试集"""
    files = {
        'test_images': 'https://drive.google.com/uc?id=1wtl-mNicxGlXZ-UQJxFnKuWPvvssQBwd',
        'gt_poses': 'https://github.com/zju3dv/LoFTR/raw/refs/heads/master/assets/scannet_test_1500/test.npz',
    }

    os.makedirs(download_dir, exist_ok=True)

    for file_name, url in files.items():
        if 'drive.google.com' in url:
            output_path = os.path.join(download_dir, f'{file_name}.tar')
            gdown.download(url, output_path, quiet=False)

            if tarfile.is_tarfile(output_path):
                print(f"Extracting {output_path}...")
                with tarfile.open(output_path, 'r:tar') as tar:
                    tar.extractall(path=download_dir)
                os.remove(output_path)
        else:
            fname = url.split('/')[-1]
            output_path = os.path.join(download_dir, fname)
            _urlretrieve(url, output_path, desc=fname)


def download_megadepth(download_dir):
    """下载 MegaDepth 完整数据集（约 500GB）"""
    # 非交互环境中通过环境变量跳过确认
    if not os.environ.get('VISIONFLOW_SKIP_CONFIRM'):
        try:
            response = input(
                "Warning: MegaDepth requires about 500 GB of free disk space. "
                "Continue? [y/n]: "
            ).strip().lower()
        except EOFError:
            print(
                "Non-interactive environment detected. "
                "Set VISIONFLOW_SKIP_CONFIRM=1 to skip confirmation."
            )
            sys.exit(1)
        if response not in ['y', 'yes']:
            print("Exiting.")
            sys.exit(0)

    os.makedirs(download_dir, exist_ok=True)

    files = {
        'train_test_indices': 'https://drive.google.com/uc?id=1YMAAqCQLmwMLqAkuRIJLDZ4dlsQiOiNA',
    }

    for file_name, url in files.items():
        output_path = os.path.join(download_dir, f'{file_name}.tar')
        gdown.download(url, output_path, quiet=False)

        if tarfile.is_tarfile(output_path):
            print(f"Extracting {output_path}...")
            with tarfile.open(output_path, 'r:tar') as tar:
                tar.extractall(path=download_dir)

    # 训练图像通过 urllib 下载
    training_data_url = (
        'https://www.cs.cornell.edu/projects/megadepth/dataset/'
        'Megadepth_v1/MegaDepth_v1.tar.gz'
    )
    training_data_path = os.path.join(download_dir, 'Megadepth_v1.tar.gz')
    _urlretrieve(training_data_url, training_data_path, desc='MegaDepth_v1.tar.gz')

    if tarfile.is_tarfile(training_data_path):
        print(f"Extracting {training_data_path}...")
        with tarfile.open(training_data_path, 'r:gz') as tar:
            tar.extractall(path=download_dir)
        os.remove(training_data_path)


def main():
    parser = argparse.ArgumentParser(
        description="数据集下载工具。链接来自 LoFTR、HPatches 和 MegaDepth 原论文。"
    )

    parser.add_argument('--megadepth', action='store_true', help="下载 MegaDepth 数据集")
    parser.add_argument('--megadepth-1500', action='store_true', help="下载 MegaDepth-1500 测试集")
    parser.add_argument('--scannet-1500', action='store_true', help="下载 ScanNet-1500 测试集")
    parser.add_argument('--hpatches', action='store_true', help="下载 HPatches 数据集（未实现）")
    parser.add_argument('--download_dir', required=True, type=str, help="下载目标目录")

    args = parser.parse_args()

    if args.megadepth:
        print(f"Downloading MegaDepth dataset to [{args.download_dir}]")
        download_megadepth(args.download_dir + '/MegaDepth')
    elif args.megadepth_1500:
        print(f"Downloading MegaDepth-1500 dataset to [{args.download_dir}]")
        download_megadepth_1500(args.download_dir + '/Mega1500')
    elif args.scannet_1500:
        print(f"Downloading ScanNet dataset to [{args.download_dir}]")
        download_scannet_1500(args.download_dir + '/ScanNet1500')
    else:
        raise RuntimeError("Dataset not implemented for download.")


if __name__ == '__main__':
    main()
