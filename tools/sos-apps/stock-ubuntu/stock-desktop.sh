#!/bin/bash
# Installs the packages of the Ubuntu desktop ISO manifest for release $1
# (e.g. 24.04), then the test tools, and adds the user "tester" with
# password-less sudo (dpkg needs root, as on a real machine).
set -u
REL=${1:?ubuntu release}
apt-get update -q
apt-get install -y -q curl ca-certificates > /dev/null
# the current point release's manifest, e.g. ubuntu-24.04.3-desktop-amd64.manifest
name=$(curl -fsSL "https://releases.ubuntu.com/$REL/" | grep -o "ubuntu-$REL[0-9.]*-desktop-amd64\.manifest" | sort -uV | tail -1)
[ -n "$name" ] || { echo "no desktop manifest for $REL"; exit 1; }
echo "manifest: $name"
curl -fsSL "https://releases.ubuntu.com/$REL/$name" | awk '{print $1}' | sed 's/:amd64$//' \
  | grep -Ev '^(linux-|grub|shim|casper|ubiquity|snapd|firefox|thunderbird|ubuntu-desktop|plymouth|cryptsetup|lvm2|mdadm|dmraid|os-prober|efibootmgr|secureboot|kpartx|zfs|initramfs|lupin|oem-|ubuntu-drivers|nvidia|cloud-init|open-vm-tools|spice|fwupd|bolt|thermald|wpasupplicant|systemd-oomd|gnome-initial-setup|snap|libsnapd|gir1.2-snapd|ubuntu-advantage|ubuntu-pro|apport|whoopsie|kerneloops|update-notifier|update-manager|unattended-upgrades|tracker|gnome-remote-desktop|ubuntu-release-upgrader)' \
  > /manifest.txt
apt-cache pkgnames | sort -u > /known.txt
sort -u /manifest.txt | comm -12 - /known.txt > /install.txt
echo "manifest packages: $(wc -l < /manifest.txt), installing: $(wc -l < /install.txt)"
echo "$name" > /stock-manifest-name
xargs -a /install.txt apt-get install -y -q --no-install-recommends -o Dpkg::Options::=--force-confold > /apt-stock.log 2>&1 \
  || { echo "bulk install failed, retrying one by one"; tail -20 /apt-stock.log;
       while read -r p; do apt-get install -y -q --no-install-recommends "$p" >> /apt-stock.log 2>&1 || echo "skip $p"; done < /install.txt; }
dpkg --configure -a >> /apt-stock.log 2>&1 || true
# test tools (not part of the product's dependencies)
apt-get install -y -q --no-install-recommends xvfb openbox xdotool x11-utils imagemagick desktop-file-utils \
    libglib2.0-bin xdg-user-dirs dbus-x11 python3 sudo procps > /apt-tools.log 2>&1 || { tail -30 /apt-tools.log; exit 1; }
dpkg-query -W -f '${Package}\t${Version}\n' > /installed-packages.txt
useradd -m -s /bin/bash tester
echo 'tester ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/tester
chmod 440 /etc/sudoers.d/tester
rm -rf /var/lib/apt/lists/*
exit 0
