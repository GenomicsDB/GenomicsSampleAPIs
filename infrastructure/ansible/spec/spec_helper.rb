require 'serverspec'


if ENV['CONTINUOUS_INTEGRATION']
    set :backend, :exec
else
    set :backend, :ssh

    if ENV['ASK_SUDO_PASSWORD']
      begin
        require 'highline/import'
      rescue LoadError
        fail "highline is not available. Try installing it."
      end
      set :sudo_password, ask("Enter sudo password: ") { |q| q.echo = false }
    else
      set :sudo_password, ENV['SUDO_PASSWORD']
    end

    host = ENV['TARGET_HOST']

    options = Net::SSH::Config.for(host)

    options[:user] ||= ENV['TARGET_USER']
    options[:port] ||= ENV['TARGET_PORT']
    options[:keys] ||= ENV['TARGET_PRIVATE_KEY']

    set :host,        options[:host_name] || host
    set :ssh_options, options
end
