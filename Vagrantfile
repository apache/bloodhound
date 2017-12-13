# -*- mode: ruby -*-
# vi: set ft=ruby :

#  Licensed to the Apache Software Foundation (ASF) under one
#  or more contributor license agreements.  See the NOTICE file
#  distributed with this work for additional information
#  regarding copyright ownership.  The ASF licenses this file
#  to you under the Apache License, Version 2.0 (the
#  "License"); you may not use this file except in compliance
#  with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing,
#  software distributed under the License is distributed on an
#  "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
#  KIND, either express or implied.  See the License for the
#  specific language governing permissions and limitations
#  under the License.

# Vagrant configuration version 2
# Please don't change it unless you know what you're doing.
Vagrant.configure(2) do |config|
  config.vm.box = "bento/ubuntu-16.04"
  config.vm.define "bloodhound"

  # Forwarded port mappings:
  # For apache served bloodhound use http://localhost:8280/
  config.vm.network :forwarded_port, guest: 80, host: 8280
  # For tracd served bloodhound on port 8000, use http://localhost:8281/
  config.vm.network :forwarded_port, guest: 8000, host: 8281

  # Sharing the salt folders with the guest VM:
  config.vm.synced_folder "salt/roots/", "/srv/"

  config.vm.provision :salt do |salt|
    # basic settings
    salt.pillar({
      "use_webserver" => true
    })

    salt.minion_config = "salt/minion"
    salt.run_highstate = true
    salt.verbose = true
  end
end
