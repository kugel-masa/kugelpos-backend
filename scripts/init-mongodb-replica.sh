#!/bin/bash
# Initialize MongoDB replica set for local development

echo "Waiting for MongoDB to start..."
sleep 5

echo "Initializing replica set..."
docker exec -it mongodb mongosh --eval "
  try {
    var status = rs.status();
    print('Replica set already initialized');
    // Check if host needs to be updated
    if (status.members[0].name !== 'mongodb:27017') {
      print('Updating replica set host...');
      var config = rs.conf();
      config.members[0].host = 'mongodb:27017';
      rs.reconfig(config, {force: true});
      print('Host updated to mongodb:27017');
    }
  } catch (e) {
    print('Initializing new replica set...');
    rs.initiate({
      _id: 'rs0',
      members: [
        { _id: 0, host: 'mongodb:27017', priority: 1 }
      ]
    });
  }
"

echo "Checking replica set status..."
sleep 2
docker exec -it mongodb mongosh --eval "rs.status()"

echo "MongoDB replica set initialized successfully!"