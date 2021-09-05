import telnetlib
import sys


class Telnet(telnetlib.Telnet):

    verbose = False

    def await(self, expected, timeout=None):
        data = self.read_until(
            expected.encode('ascii'), timeout=timeout)

        data = data.decode('ascii')
        data = '\n'.join(filter(None, data.splitlines()))
        if self.verbose:
            sys.stdout.write(data)
        return data

    def send(self, data):
        if self.verbose:
            sys.stdout.write(data)
        self.write(data.encode('ascii'))

    def await_send(self, expected, answer, timeout=None, fallback='\r'):
        res = self.await(expected, timeout=timeout)
        if expected in res:
            self.send(answer)
            return True
        elif fallback:
            self.send(fallback)
            return False
        return False


def flash(telnet_host, telnet_port, password=''):
    _password = password.encode('ascii')
    tn = None
    try:
        try:
            tn = telnetlib.Telnet(telnet_host, int(telnet_port))
        except IOError:
            raise Exception(f'Port occupied')
        tn.write(b'\r')
        # Initial configuration dialog is the ':'
        case, _, alt = tn.expect([b'\[yes/no\]:', b'>', ], timeout=10)
        if case == 0:
            tn.write(b'no\r\r')
        elif case == -1 and alt == b'':
            raise Exception(f'Not connected')
        elif case == -1 and alt == b'\n\rswitch: ':
            raise Exception(f'Rom mode')
        elif case == -1:
            raise Exception(f'Booting {alt[:48]}')
        tn.write(b'enable\r\r')
        case, _, _ = tn.expect([b'Password: ', b'.*# ', ], timeout=5)
        if case == 0:
            tn.write(_password + b'\r')
            case, _, _ = tn.expect(
                [b'Password: ', b'Access denied'], timeout=2)
            if case != -1:
                raise Exception(f"Wrong password '{password}'")
        tn.write(b'terminal length 0\r\r')
        tn.write(b'show ver\r')
        case, _, _ = tn.expect([b'Version 12.1\(22\)EA14'], timeout=16)
        if case == -1:
            raise Exception(f'Wrong firmware version')

        tn.write(b'delete flash:vlan.dat\r\r\r')
        # tn.write(b'wr erase\r\r')
        tn.write(b'erase startup-config\r\r')
        tn.write(b'reload\r\r')
        case, _, _ = tn.expect([b'\[yes\/no\]:'], timeout=12)
        if case == 0:
            tn.write(b'no\r')
        tn.write(b'\r\r')

        case, _, _ = tn.expect([b'\[yes\/no\]:'], timeout=120)
        if case == -1:
            raise Exception(f'Startup failed')

    except:
        if tn:
            tn.write(b'exit\r\r')
        raise
    finally:
        if tn:
            tn.close()


def configure(
        telnet_host,
        telnet_port,
        hostname,
        mgmt,
        gw,
        snmp_community,
        enable_password,
        access_password,
):
    tn = Telnet(telnet_host, telnet_port)
    tn.write(b'\r')
    tn.await_send('initial configuration dialog? [yes/no]:', 'no\r\r', timeout=120)  # noqa
    tn.await_send('>', 'enable\r\r')
    tn.await_send('#', 'conf t\r')
    tn.await_send('config', f'hostname {hostname}\r')
    tn.await_send('config', "banner login ^\r")
    tn.await_send('Enter TEXT message', "Go Away\r^\r")
    tn.await_send("config", "service timestamps debug datetime localtime\r")
    tn.await_send("config", "service timestamps log datetime localtime\r")
    tn.await_send("config", "service password-encryption\r")
    tn.await_send("config", "clock timezone CET 1\r")
    tn.await_send("config", "clock summer-time CET recurring last Sun Mar 2:00 last Sun Oct 3:00\r")  # noqa
    tn.await_send("config", "aaa new-model\r")
    tn.await_send("config", f"enable secret {enable_password}\r")
    tn.await_send("config", f"username admin privilege 15 secret {access_password}\r")  # noqa
    tn.await_send("config", "no ip domain-lookup\r")
    tn.await_send("config", "ip domain-name access.npf\r")
    tn.await_send("config", "crypto key generate rsa mod 1024\r")
    tn.await_send("config", "ip ssh version 2\r")
    tn.await_send("config", "vtp mode transparent\r")
    tn.await_send("config", "spanning-tree portfast default\r")
    tn.await_send("config", "spanning-tree portfast bpduguard default\r")
    tn.await_send("config", "spanning-tree extend system-id\r")
    tn.await_send("config", "spanning-tree mst configuration\r")
    tn.await_send("config-mst", "revision 5\r")
    tn.await_send("config-mst", "instance 10 vlan 1-1024\r")
    tn.await_send("config-mst", "spanning-tree mode mst\r")

    tn.await_send("config", "errdisable recovery cause all\r")
    tn.await_send("config", "no errdisable recovery cause psecure-violation\r")
    tn.await_send("config", "no ip http server\r")
    tn.await_send("config", "no cdp advertise-v2\r")

    tn.await_send("config", "vlan 10\r")
    tn.await_send("config-vlan", "name ACCESS\r")
    tn.await_send("config-vlan", "vlan 193\r")
    tn.await_send("config-vlan", "name MGMT\r")

    tn.await_send("config-vlan", "int range fa0/1 -24\r")
    tn.await_send("config-if-range", "no cdp enable\r")
    tn.await_send("config-if-range", "switchport access vlan 10\r")
    tn.await_send("config-if-range", "switchport mode access\r")
    tn.await_send("config-if-range", "no logging event link-status\r")
    tn.await_send("config-if-range", "switchport port-security maximum 3\r")
    tn.await_send("config-if-range", "switchport port-security violation restrict\r")  # noqa
    tn.await_send("config-if-range", "switchport port-security\r")
    tn.await_send("config-if-range", "no shutdown\r")

    tn.await_send("config-if-range", "int ra gi0/1 -2\r")
    tn.await_send("config-if-range", "ip dhcp snooping trust\r")
    tn.await_send("config-if-range", "switchport mode trunk\r")
    tn.await_send("config-if-range", "switchport trunk native vlan 10\r")
    tn.await_send("config-if-range", "switchport trunk allowed vlan 10,193\r")
    tn.await_send("config-if-range", "switchport nonegotiate\r")
    tn.await_send("config-if-range", "cdp enable\r")
    tn.await_send("config-if-range", "no shutdown\r")

    tn.await_send("config-if-range", "int vl 193\r")
    tn.await_send("config-if", f"ip add {mgmt} 255.255.255.0\r")
    tn.await_send("config-if", "no shutdown\r")
    tn.await_send("config-if", f"ip default-gateway {gw}\r")

    tn.await_send("config", "ip access-list standard PERMIT_MANAGEMENT_ONLY\r")
    tn.await_send("config-std-nacl", "permit 10.97.0.15 0.0.0.0\r")
    tn.await_send("config-std-nacl", "permit 10.97.0.20 0.0.0.0\r")
    tn.await_send("config-std-nacl", "permit 10.248.248.0 0.0.3.255\r")
    tn.await_send("config-std-nacl", "permit 10.254.11.0 0.0.0.255\r")

    tn.await_send("config-std-nacl", f"snmp-server community {snmp_community} RO 1\r")
    tn.await_send("config", f"snmp-server host 10.0.1.13 traps version 2c {snmp_community}\r")  # noqa
    tn.await_send("config", f"snmp-server host 10.0.1.140 traps version 2c {snmp_community}\r")  # noqa
    tn.await_send("config", f"snmp-server host 10.97.0.20 version 2c {snmp_community}\r")  # noqa
    tn.await_send("config", "snmp-server ifindex persist\r")
    tn.await_send("config", f"snmp-server location {hostname}\r")

    tn.await_send("config", "snmp-server enable traps envmon\r")
    tn.await_send("config", "snmp-server enable traps mac-notification\r")
    tn.await_send("config", "snmp-server enable traps port-security\r")
    tn.await_send("config", "snmp-server enable traps snmp\r")
    tn.await_send("config", "snmp-server enable traps syslog\r")

    tn.await_send("config", "logging 10.97.0.10\r")
    tn.await_send("config", "logging buffered 8192 debugging\r")

    tn.await_send("config", "ntp server 10.255.255.254 prefer\r")
    tn.await_send("config", "ntp server 10.255.255.255 source Vlan193\r")

    tn.await_send("config", "ip dhcp snooping vlan 2 1000\r")
    tn.await_send("config", "no ip dhcp snooping information option\r")
    tn.await_send("config", "ip dhcp snooping\r")

    tn.await_send("config", "line vty 0 15\r")
    tn.await_send("config-line", "access-class PERMIT_MANAGEMENT_ONLY in\r")
    tn.await_send("config-line", "transport input ssh\r")
    tn.await_send("config-line", "logging synchronous\r")

    tn.await_send("config-line", "end\r")

    tn.await_send("#", "wr mem\r")
    tn.await_send('#', 'exit\r\r')
    tn.await_send('#', 'exit\r\r')
    tn.await_send('RETURN', '\r\r')
    tn.await_send('>', 'exit\r\r')
    tn.await_send('RETURN', '\r\r')

    tn.close()


if __name__ == '__main__':
    flash('192.168.0.250', 2001, password='')
