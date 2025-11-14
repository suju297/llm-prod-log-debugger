const jwt = require('jsonwebtoken');
const config = require('./config');

class AuthMiddleware {
    constructor(userService) {
        this.userService = userService;
    }
    
    async validateToken(req, res, next) {
        const token = req.headers.authorization?.split(' ')[1];
        
        if (!token) {
            return res.status(401).json({ error: 'No token provided' });
        }
        
        try {
            const decoded = jwt.verify(token, config.JWT_SECRET);
            const user = await this.userService.getUserDetails(decoded.userId);
            
            if (!user) {
                return res.status(401).json({ error: 'Invalid token' });
            }
            
            req.user = user;
            next();
        } catch (error) {
            console.error('Auth validation failed:', error);
            return res.status(401).json({ error: 'Invalid token' });
        }
    }
}

module.exports = AuthMiddleware;