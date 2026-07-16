# CitiBike-Analytics-Pipeline

#### Originally, I wanted to create a Unity Catalog Storage Credential and External Location for S3. These administrative features are not supported in Databricks Free Edition, so the pipeline reads the raw data using the available storage access mechanism while maintaining the same Bronze, Silver, Gold architecture