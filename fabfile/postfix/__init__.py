from fabric.api import task, env
from .. import system

__all__ = ['install']


@task
def install(relay=None):
    """
    Deploy postfix for outbound SMTP
    """

    if relay is None:
        relay = env.smtp_relay

    # set the mailer type
    system.sudo('debconf-set-selections <<< "postfix postfix/main_mailer_type string \'%s\'"' % (
        'Satellite' if relay else 'Internet Site'
    ))
    system.sudo("debconf-set-selections <<< 'postfix postfix/mailname string %s'" % env.host)

    # configure the relayhost or mailname, as required
    if relay:
        system.sudo("debconf-set-selections <<< 'postfix postfix/relayhost %s'" % relay)

    #else:
    #    system.sudo("debconf-set-selections <<< 'postfix postfix/mailname string %s'" % env.host)

    # install postfix
    system.apt('postfix')

    # enforce the config after installation, JIC it has changed
    if relay:
        system.sudo("/usr/sbin/postconf -e relayhost=%s" % relay)

    system.sudo("/usr/sbin/postfix reload")
