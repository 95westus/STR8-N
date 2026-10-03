"""Alpha24-derived F-pocket regression; host model only."""
import sys
import build_v2_config as firmware
sys.modules['build_v2'] = firmware
sys.modules['build_v2_a24'] = firmware
sys.modules['build_v2_a23'] = firmware
import test_v2_a24_regression as regression

if __name__ == '__main__':
    regression.main()
    (firmware.OUT / 'a24-regression.json').replace(firmware.OUT / 'config-regression.json')
