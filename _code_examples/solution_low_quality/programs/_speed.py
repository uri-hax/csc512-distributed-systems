import subprocess
import time

t0 = time.time()
subprocess.run(['./_speed.sh'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
t1 = time.time()
print("Test took how many seconds to run?")
print(t1-t0)