package com.example;

public class UserService {
    private final UserRepository userRepository;
    private final ProfileService profileService;
    
    public UserService(UserRepository userRepository, ProfileService profileService) {
        this.userRepository = userRepository;
        this.profileService = profileService;
    }
    
    public UserDetails getUserDetails(Long userId) {
        User user = userRepository.findById(userId);
        
        if (user == null) {
            throw new UserNotFoundException("User not found: " + userId);
        }
        
        // Fetch profile - may return null for new users
        user.profile = profileService.getProfile(userId);
        
        UserDetails details = new UserDetails();
        details.setId(user.getId());
        details.setEmail(user.getEmail());
        details.setName(user.profile.getName()); // Line 42 - NPE here!
        details.setCreatedAt(user.getCreatedAt());
        
        return details;
    }
}