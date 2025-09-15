export default function handler(req, res) {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Content-Type', 'application/json');
    
    const response = {
        message: "Hello from Node.js!",
        status: "API is working!",
        timestamp: new Date().toISOString()
    };
    
    res.status(200).json(response);
}