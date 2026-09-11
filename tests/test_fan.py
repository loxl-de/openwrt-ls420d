"""Exercise actual shell worker against a fake sysfs; never touch real hardware."""
from pathlib import Path
import subprocess
import tempfile
import unittest

BASE = Path(__file__).resolve().parents[1]
FILES = BASE / 'openwrt/files'
POLICY = FILES / 'usr/libexec/ls420d-fan-policy.sh'
WORKER = FILES / 'usr/sbin/ls420d-fan'


class FanTests(unittest.TestCase):
    def curve(self, t, old, thresholds=(60000, 65000, 75000, 4000)):
        command = f'. "{POLICY}"; fan_curve ' + ' '.join(map(str, (t, old, *thresholds)))
        return int(subprocess.check_output(['busybox', 'ash', '-c', command]))

    def test_curve_boundaries(self):
        for t, state in [(59000, 0), (60000, 1), (64999, 1), (65000, 2), (75000, 3)]:
            self.assertEqual(self.curve(t, 0), state)

    def test_hysteresis(self):
        for temp, old, state in [(71000, 3, 3), (70999, 3, 2), (61000, 2, 2),
                                  (60999, 2, 1), (56000, 1, 1), (55999, 1, 0)]:
            self.assertEqual(self.curve(temp, old), state)

    def simulate(self, cpu='54000', phy='43000', disk='25000', cycles=16,
                 alarm='0', missing_disk=False, governor=True, disk_state='active/idle'):
        with tempfile.TemporaryDirectory(prefix='fan-fixture-') as tmp:
            root = Path(tmp)
            def put(name, value):
                path = root/name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(value + '\n')
                return path
            fan = root/'sys/class/thermal/cooling_device0'
            for name, val in [('type', 'gpio-fan'), ('max_state', '3'), ('cur_state', '0')]:
                put('sys/class/thermal/cooling_device0/'+name, val)
            put('sys/class/thermal/thermal_zone0/mode', 'enabled')
            if governor:
                put('sys/class/thermal/thermal_zone0/policy', 'step_wise')
            (root/'sys/class/thermal/thermal_zone0/cdev0').symlink_to(fan)
            for i, (name, temp) in enumerate([
                ('d0018300.thermal', cpu), ('d0072004mdiomii00', phy), ('drivetemp', disk)]):
                if name == 'drivetemp' and missing_disk:
                    continue
                put(f'sys/class/hwmon/hwmon{i}/name', name)
                if temp is not None:
                    put(f'sys/class/hwmon/hwmon{i}/temp1_input', temp)
                if name == 'drivetemp':
                    (root/f'sys/class/hwmon/hwmon{i}/device/block/sda').mkdir(parents=True)
            put('sys/class/hwmon/hwmon4/name', 'gpio_fan')
            put('sys/class/hwmon/hwmon4/fan1_alarm', alarm)
            put('sys/block/sda/device/vendor', 'ATA')
            clock = put('uptime', '600 0')
            put('sys/class/rtc/rtc0/wakealarm', '12345')
            (root/'run').mkdir()
            policy = POLICY.read_text().replace('/sys/', str(root/'sys')+'/')
            policy = policy.replace('/proc/uptime', str(clock)).replace('/sbin/poweroff', 'test_poweroff')
            (root/'policy').write_text(policy)
            worker = WORKER.read_text().replace('/usr/libexec/ls420d-fan-policy.sh', str(root/'policy'))
            worker = worker.replace('/sys/', str(root/'sys')+'/').replace('RUN=/var/run/ls420d-fan', f'RUN={root}/run')
            prelude = f'''
test_count=0
logger() {{ :; }}
test_poweroff() {{ echo requested >>{root}/shutdown; }}
hdparm() {{ echo "$2:"; echo " drive state is:  {disk_state}"; echo "$2" >>{root}/hdparm-calls; }}
sleep() {{
    test_count=$((test_count+1))
    [ "$test_count" -lt {cycles} ] || exit 0
    echo "$((600+test_count*5)) 0" >{clock}
}}
'''
            script = root/'worker'
            script.write_text(prelude + worker)
            result = subprocess.run(['busybox', 'ash', str(script), 'worker'],
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            status = dict(word.split('=', 1) for word in (root/'run/status').read_text().split())
            zone = root/'sys/class/thermal/thermal_zone0'
            status['zone_mode'] = (zone/'mode').read_text().strip()
            status['zone_policy'] = (zone/'policy').read_text().strip() if governor else ''
            status['hdparm_calls'] = (root/'hdparm-calls').read_text().count('/dev/sda') if (root/'hdparm-calls').exists() else 0
            return status, (root/'shutdown').exists(), (root/'sys/class/rtc/rtc0/wakealarm').read_text().strip()

    def test_cool_fan_off_after_hold(self):
        status, shutdown, _ = self.simulate()
        self.assertEqual(status['state'], '0')
        self.assertFalse(shutdown)

    def test_initial_full_cooling_hold(self):
        status, _, _ = self.simulate(cycles=5)
        self.assertEqual(status['state'], '3')

    def test_cpu_low_medium_high(self):
        for temp, state in [('62000', '1'), ('67000', '2'), ('77000', '3')]:
            status, shutdown, _ = self.simulate(cpu=temp)
            self.assertEqual(status['state'], state)
            self.assertFalse(shutdown)

    def test_hottest_sensor_wins(self):
        status, _, _ = self.simulate(cpu='57000', phy='68000', disk='49000')
        self.assertEqual(status['state'], '3')

    def test_bad_cpu_fails_full(self):
        for temp in [None, 'broken', '0', '-1000', '999999']:
            status, _, _ = self.simulate(cpu=temp)
            self.assertEqual((status['state'], status['fault']), ('3', '1'))

    def test_detected_disk_without_sensor_fails_full(self):
        status, _, _ = self.simulate(missing_disk=True)
        self.assertEqual(status['fault'], '1')

    def test_missing_phy_fails_full(self):
        status, _, _ = self.simulate(phy=None)
        self.assertEqual((status['state'], status['fault']), ('3', '1'))

    def test_fan_alarm_fails_full(self):
        status, _, _ = self.simulate(alarm='1')
        self.assertEqual((status['state'], status['fault']), ('3', '1'))

    def test_critical_temperatures_request_shutdown(self):
        for kw in [{'cpu': '90000'}, {'disk': '60000'}, {'phy': '100000'}]:
            _, shutdown, wakealarm = self.simulate(**kw)
            self.assertTrue(shutdown)
            self.assertEqual(wakealarm, '0')

    def test_hard_cpu_limit_immediate(self):
        _, shutdown, _ = self.simulate(cpu='95000', cycles=1)
        self.assertTrue(shutdown)

    def test_persistent_sensor_fault_shutdown(self):
        _, shutdown, _ = self.simulate(cpu=None, cycles=27)
        self.assertTrue(shutdown)

    def test_zone_keeps_kernel_critical_trip_via_user_space_governor(self):
        status, _, _ = self.simulate()
        self.assertEqual((status['zone_policy'], status['zone_mode']), ('user_space', 'enabled'))

    def test_zone_disabled_without_user_space_governor(self):
        status, _, _ = self.simulate(governor=False)
        self.assertEqual(status['zone_mode'], 'disabled')

    def test_sleeping_disk_is_not_polled(self):
        status, shutdown, _ = self.simulate(disk='49000', disk_state='standby')
        self.assertEqual((status['state'], status['fault'], status['hdd_max_mC']), ('0', '0', '0'))
        self.assertFalse(shutdown)
        self.assertGreater(status['hdparm_calls'], 0)

    def test_awake_disk_is_polled(self):
        status, _, _ = self.simulate(disk='49000')
        self.assertEqual((status['state'], status['hdd_max_mC']), ('3', '49000'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
