# Common public email-provider catalog

Catalog version: `2026-08-24-v1`

This bounded catalog supports the code-owned
`possible_email_domain_typo` observation. It is not a list of all valid email
providers and is never used to infer mailbox validity, identity, fraud, or
physical location. Exact catalog domains and arbitrary custom domains produce
no observation. A close match only asks the recruiter to confirm the address
and has zero scoring weight.

| Family | Reviewed domains and aliases | Official source |
| --- | --- | --- |
| Google | `gmail.com` | [Gmail Help](https://support.google.com/mail/answer/56256) |
| Microsoft | `outlook.com`, `hotmail.com`, `live.com`, `msn.com` | [Microsoft Support](https://support.microsoft.com/en-us/outlook/add-or-remove-an-email-alias-in-outlook-com) |
| Yahoo | `yahoo.com`, `myyahoo.com`, `yahoo.co.uk`, `yahoo.fr` | [Yahoo Help](https://help.yahoo.com/kb/SLN2153.html) |
| Proton | `proton.me`, `protonmail.com`, `pm.me`, `protonmail.ch` | [Proton Support](https://proton.me/support/addresses-and-aliases) |
| Apple | `icloud.com`, `me.com`, `mac.com` | [Apple Support](https://support.apple.com/en-lamr/118230) |
| Zoho | `zohomail.com` | [Zoho Mail](https://www.zoho.com/mail/how-to/create-an-email-account.html) |
| Onet | `onet.pl`, `op.pl` | [Onet Poczta terms](https://pomoc.poczta.onet.pl/wp-content/uploads/2024/08/Regulamin_Onet_Poczta_20240812.pdf) |
| WP/o2 | `wp.pl`, `o2.pl`, `tlen.pl` | [WP account help](https://pomoc.wp.pl/1login/nowe-konto-1login-z-nowym-adresem-pocztowym), [WP history](https://holding.wp.pl/historia) |
| Interia | `interia.pl`, `interia.eu`, `interia.com`, `poczta.fm`, `vip.interia.pl`, `intmail.pl`, `interiowy.pl`, `adresik.net`, `pisz.to`, `pacz.to`, `ogarnij.se` | [Interia configuration help](https://pomoc.poczta.interia.pl/popularne-artykuly/news-parametry-do-konfiguracji-programow-pocztowych,nId,2136275) |

To change the catalog, update the source-backed entries, bump the catalog
version, review close-match collisions, and run the exact-domain, custom-domain,
and `gmail.cm` regression tests before release.
