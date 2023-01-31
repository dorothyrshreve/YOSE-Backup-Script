# YOSE-Backup-Script
This script downloads zipped files containing JSONs of all the items from specified groups on AGOL or Portal. 
It is being run nightly at Yosemite National Park, but can be scheduled as frequently as you'd like.

## To set up the script:
  - download it
  - fill in some headless account information in the yaml configuration file
  - create a folder to log script outputs
  - create a folder to hold downloads
  - create some groups on AGOL and Portal that users can share their items with
  - document that group name, platform, and ID in the Group csv
  - schedule the task to run
  - have the task run
  - check out the logs and make sure everything is good to go

Once the script is set up, all users have to do is share the items they would like backed up with the established AGOL or Portal groups.
These items are brought down by the script into the backup folders on a local drives that can be protected if necessary (for sensitive content).

The zipped files can be extracted with an ArcGIS Toolbox tool by just about anyone so users are pretty much self-sufficient.

## Heads Ups:
  - the script will not download attachments
  - globalid field types are converted to text fields (relationships can be remade but new connections may not generate for new records)
  - there is no built in testing to ensure large content gets removed from script
