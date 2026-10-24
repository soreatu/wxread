FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 设置时区为中国时区
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

ENV PATH="/usr/local/bin:${PATH}"

# 复制项目文件
COPY main.py push.py config.py cookie_store.py log_utils.py scheduler.py ./

# 安装 Python 依赖
RUN python -m pip install --no-cache-dir \
    'requests>=2.32.3' \
    'urllib3>=2.2.3' \
    'cryptography==50.0.2' \
    'APScheduler>=3.10,<4'

# APScheduler 默认每天北京时间 06:30 运行，可通过 CRON_SCHEDULE 调整
CMD ["python", "scheduler.py"]
