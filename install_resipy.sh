echo "Installing ResIPy (cloning git, adding python packages)"
source ohmpy/bin/activate
which pip
sudo apt-get install wine --assume-yes
cd ..
git clone -b rpi https://gitlab.com/hkex/resipy
pip install numpy matplotlib scipy pandas requests psutil
cd OhmPi
