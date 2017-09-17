import concurrent.futures
import csv
import threading
import time
import os

import cisco2950t


class Batch:

    def __init__(self, offset, size):
        self.offset = offset
        self.size = size
        self.batch_status = [''] * size
        self.oks = [False] * size
        self.lock = threading.Lock()
        self.preflight_executor = \
            concurrent.futures.ThreadPoolExecutor(max_workers=size)

        with open('switches.csv', newline='') as f:
            reader = csv.reader(f)
            config = [row for row in reader]

        self.config = config[offset: offset + size]

        self.telnet_host = '192.168.0.250'
        self.telnet_base_port = 2000

        self.snmp_community = ''
        self.enable_password = ''
        self.access_password = ''

    def configure(self):

        def _preflight(telnet_host, telnet_port, enable_password):
            index = telnet_port - 2000 - 1
            while True:
                try:
                    cisco2950t.flash(
                        telnet_host=telnet_host,
                        telnet_port=telnet_port,
                        password=enable_password)
                    with self.lock:
                        self.batch_status[index] = \
                            f'{index + 1: >2}: {self.config[index][0]} - Preflight succeeded'
                        # print(index)
                        self.oks[index] = True
                    break
                except Exception as e:
                    with self.lock:
                        self.batch_status[index] = f'{index + 1: >2}: {self.config[index][0]} - ' + str(e)
                    time.sleep(5)

        for n in range(self.size):

            self.preflight_executor.submit(
                _preflight,
                self.telnet_host,
                self.telnet_base_port + n + 1,
                self.enable_password,
            )
            with self.lock:
                self.batch_status[n] = f'{n + 1: >2}: {self.config[n][0]} - Processing'

        while not all(self.oks):
            os.system("printf '\033c'")
            print(self)
            time.sleep(10)

        time.sleep(5)

        os.system("printf '\033c'")
        for n, c in enumerate(self.config):
            n = n+1
            print(f'{n: >2} - {c[0]: <25} mgnt={c[1]: <15} gw={c[2]: <15}')
            if n == 8:
                print('-----------------------------------------------')
        print('\n--\nWait while writing configuration to switches...')
        for n in range(self.size):
            self.preflight_executor.submit(
                cisco2950t.configure,
                self.telnet_host,
                self.telnet_base_port + n + 1,
                self.config[n][0],  # hostname
                self.config[n][1],  # management
                self.config[n][2],  # gateway
                self.snmp_community,
                self.enable_password,
                self.access_password,
            )
        self.preflight_executor.shutdown(wait=True)

    def __str__(self):
        return '\n'.join(self.batch_status)


if __name__ == '__main__':
    import sys
    start_index = int(sys.argv[1]) * 16

    b = Batch(start_index, 11)
    b.configure()
