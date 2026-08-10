import socket

def scan_ports(host, start_port, end_port):
    open_ports = []
    for port in range(start_port, end_port + 1):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((host, port))
            if result == 0:
                open_ports.append(port)
            sock.close()
        except socket.error as e:
            print(f"Error: {e}")
    return open_ports

host = input("Enter the host IP address: ")
start_port = int(input("Enter the start port number: "))
end_port = int(input("Enter the end port number: "))

open_ports = scan_ports(host, start_port, end_port)
print(f"Open ports: {open_ports}")