%global _hardened_build 1

%{expand: %(NIF_VER=`rpm -q erlang-erts --provides | grep --color=no erl_nif_version` ; if [ "$NIF_VER" != "" ]; then echo %%global __erlang_nif_version $NIF_VER ; fi)}
%{expand: %(DRV_VER=`rpm -q erlang-erts --provides | grep --color=no erl_drv_version` ; if [ "$DRV_VER" != "" ]; then echo %%global __erlang_drv_version $DRV_VER ; fi)}

Name:           ejabberd
Version:        15.10
Release:        1%{?dist}.collab
Summary:        A distributed, fault-tolerant Jabber/XMPP server

Group:          Applications/Internet
License:        GPLv2+
URL:            http://www.ejabberd.im/
Source0:        https://www.process-one.net/downloads/%{name}/%{version}/%{name}-%{version}.tgz
Source1:        ejabberd.init
Source2:        ejabberd.logrotate
Source3:        ejabberd.sysconfig
Source4:        ejabberdctl.pam
Source5:        ejabberd.pam

Patch1:         ejabberd-configure.patch
Patch2:         ejabberd-makefile.patch
Patch3:         ejabberd-ejabberdctl.patch
Patch4:         ejabberd-collab.patch

BuildRequires:  expat-devel
BuildRequires:  openssl-devel >= 0.9.8
BuildRequires:  pam-devel
BuildRequires:  libyaml-devel
BuildRequires:  erlang
BuildRequires:  git
BuildRequires:  autoconf
BuildRequires:  automake

# For creating user and group
Requires(pre):  shadow-utils

Requires(post): /usr/bin/openssl
Requires(post): /sbin/chkconfig
Requires(preun): /sbin/chkconfig
Requires(preun): /sbin/service
Requires(postun): /sbin/service

Provides:       user(%{name})
Provides:       group(%{name})

Requires:       erlang
Requires:       util-linux
Requires:       usermode
%{?__erlang_drv_version:Requires: %{__erlang_drv_version}}
%{?__erlang_nif_version:Requires: %{__erlang_nif_version}}

%description
ejabberd is a Free and Open Source distributed fault-tolerant
Jabber/XMPP server. It is mostly written in Erlang, and runs on many
platforms (tested on Linux, FreeBSD, NetBSD, Solaris, Mac OS X and
Windows NT/2000/XP).

%prep
%setup -q

%patch1 -p1 -b .configure
%patch2 -p1 -b .makefile
%patch3 -p1 -b .ejabberdctl
%patch4 -p1 -b .collab

%build
autoreconf -ivf

%configure --enable-nif --enable-odbc --enable-mysql --enable-pgsql --enable-pam --enable-zlib --enable-iconv --enable-debug --enable-lager
make

%install
make install DESTDIR=%{buildroot}

find %{buildroot}/%{_libdir} -type f -name *.so -execdir chmod 755 -- {} +

# fix example SSL certificate path to real one, which we created recently (see above)
%{__perl} -pi -e 's!/path/to/ssl.pem!/etc/ejabberd/ejabberd.pem!g' %{buildroot}/etc/ejabberd/ejabberd.yml

# fix captcha path
%{__perl} -pi -e 's!/lib/ejabberd/priv/bin/captcha.sh!%{_libdir}/%{name}/ejabberd/priv/bin/captcha.sh!g' %{buildroot}/etc/ejabberd/ejabberd.yml

# install pam config
install -D -p -m 0644 %{S:4} %{buildroot}%{_sysconfdir}/pam.d/ejabberdctl
install -D -p -m 0644 %{S:5} %{buildroot}%{_sysconfdir}/pam.d/ejabberd

# install init-script
install -D -p -m 0755 %{S:1} %{buildroot}%{_initrddir}/ejabberd
# install sysconfig file
install -D -p -m 0644 %{S:3} %{buildroot}%{_sysconfdir}/sysconfig/ejabberd
# install config for logrotate
install -D -p -m 0644 %{S:2} %{buildroot}%{_sysconfdir}/logrotate.d/ejabberd

%pre
getent group %{name} >/dev/null || groupadd -r %{name}
getent passwd %{name} >/dev/null || \
useradd -r -g %{name} -d %{_localstatedir}/lib/%{name} -s /sbin/nologin -M \
-c "ejabberd" %{name} 2>/dev/null || :

if [ $1 -gt 1 ]; then
	# we should backup DB in every upgrade
	if ejabberdctl status >/dev/null ; then
		# Use timestamp to make database restoring easier
		TIME=$(date +%%Y-%%m-%%dT%%H:%%M:%%S)
		BACKUPDIR=$(mktemp -d -p /var/tmp/ ejabberd-$TIME.XXXXXX)
		chown ejabberd:ejabberd $BACKUPDIR
		BACKUP=$BACKUPDIR/ejabberd-database
		ejabberdctl backup $BACKUP
		# Change ownership to root:root because ejabberd user might be
		# removed on package removal.
		chown -R root:root $BACKUPDIR
		chmod 700 $BACKUPDIR
		echo
		echo The ejabberd database has been backed up to $BACKUP.
		echo
	fi
fi

%post
if [ $1 -eq 1 ]; then
	# Initial installation
	/sbin/chkconfig --add %{name} || :
fi

# Create SSL certificate with default values if it doesn't exist
(cd /etc/ejabberd
if [ ! -f ejabberd.pem ]
then
    echo "Generating SSL certificate /etc/ejabberd/ejabberd.pem..."
    HOSTNAME=$(hostname -s 2>/dev/null || echo "localhost")
    DOMAINNAME=$(hostname -d 2>/dev/null || echo "localdomain")
    openssl req -new -x509 -days 365 -nodes -out ejabberd.pem \
                -keyout ejabberd.pem > /dev/null 2>&1 <<+++
.
.
.
$DOMAINNAME
$HOSTNAME
ejabberd
root@$HOSTNAME.$DOMAINNAME
+++
chown ejabberd:ejabberd ejabberd.pem
chmod 600 ejabberd.pem
fi)

%preun
if [ $1 -eq 0 ]; then
	# Package removal, not upgrade
        /sbin/service %{name} stop >/dev/null 2>&1 || :
        /sbin/chkconfig --del %{name} || :
fi

%postun
if [ $1 -ge 1 ]; then
	# Package upgrade, not uninstall
	/sbin/service %{name} condrestart >/dev/null 2>&1
fi

%files
%doc COPYING

%attr(750,ejabberd,ejabberd) %dir %{_sysconfdir}/ejabberd
%attr(640,ejabberd,ejabberd) %config(noreplace) %{_sysconfdir}/ejabberd/ejabberd.yml
%attr(640,ejabberd,ejabberd) %config(noreplace) %{_sysconfdir}/ejabberd/ejabberdctl.cfg
%attr(640,ejabberd,ejabberd) %config(noreplace) %{_sysconfdir}/ejabberd/inetrc

%config(noreplace) %{_sysconfdir}/sysconfig/%{name}
%{_initrddir}/%{name}

%config(noreplace) %{_sysconfdir}/logrotate.d/%{name}
%config(noreplace) %{_sysconfdir}/pam.d/%{name}
%config(noreplace) %{_sysconfdir}/pam.d/ejabberdctl
%{_sbindir}/ejabberdctl

%dir %{_libdir}/%{name}
%{_libdir}/%{name}/*/ebin
%{_libdir}/%{name}/*/include
%{_libdir}/%{name}/*/priv
%attr(4750,root,ejabberd) %{_libdir}/%{name}/p1_pam/priv/bin/epam

%attr(750,ejabberd,ejabberd) %dir /var/lib/ejabberd
%attr(750,ejabberd,ejabberd) %dir /var/lock/ejabberdctl
%attr(750,ejabberd,ejabberd) %dir /var/log/ejabberd

%changelog
* Wed Nov 11 2015 Ossi Salmi <osalmi@iki.fi> - 15.10-1
- Ver. 15.10
